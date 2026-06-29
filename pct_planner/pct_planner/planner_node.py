import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from nav_msgs.msg import Path
from geometry_msgs.msg import PointStamped, Pose, PoseStamped, PoseWithCovarianceStamped
try:
    from interactive_markers.interactive_marker_server import InteractiveMarkerServer
except ImportError:
    from interactive_markers import InteractiveMarkerServer
from visualization_msgs.msg import (
    InteractiveMarker,
    InteractiveMarkerControl,
    InteractiveMarkerFeedback,
    Marker,
    MarkerArray,
)

from pct_planner.utils import traj2ros
from pct_planner.planner_wrapper import TomogramPlanner
from pct_planner.config import Config

class PCTPlanner(Node):
    def __init__(self):
        super().__init__('pct_planner')
        
        # Declare parameters
        self.declare_parameter("rsg_root", rclpy.Parameter.Type.STRING)
        self.declare_parameter("scene_name", "Plaza")
        self.declare_parameter("tomo_file", "")
        self.declare_parameter("path_topic", "/pct_path")
        self.declare_parameter("start_topic", "/initialpose")
        self.declare_parameter("goal_topic", "/goal_pose")
        self.declare_parameter("clicked_point_topic", "/clicked_point")
        self.declare_parameter("clicked_point_mode", "alternate")
        self.declare_parameter("plan_on_startup", False)
        self.declare_parameter("enable_interactive_markers", True)
        self.declare_parameter("interactive_marker_namespace", "/pct_waypoints")
        self.declare_parameter("snap_search_radius_cells", 10)
        self.declare_parameter("snap_to_traversable_layer", True)
        self.declare_parameter("plan_on_marker_release", True)
        
        # Get parameters
        rsg_root_param = self.get_parameter("rsg_root")
        if rsg_root_param.value is None:
            self.get_logger().error("Missing required parameter: rsg_root")
            raise ValueError("Missing required parameter: rsg_root")
        self.rsg_root = rsg_root_param.get_parameter_value().string_value
        
        scene_name = self.get_parameter("scene_name").get_parameter_value().string_value
        self.get_logger().info(f"Using scene: {scene_name}")
        
        # Scene configuration
        self.configure_scene(scene_name)

        tomo_file = self.get_parameter("tomo_file").get_parameter_value().string_value
        if tomo_file:
            self.tomo_file = tomo_file
        
        self.cfg = Config()
        
        qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL
        )

        self.path_topic = self.get_parameter("path_topic").get_parameter_value().string_value
        self.start_topic = self.get_parameter("start_topic").get_parameter_value().string_value
        self.goal_topic = self.get_parameter("goal_topic").get_parameter_value().string_value
        self.clicked_point_topic = self.get_parameter("clicked_point_topic").get_parameter_value().string_value
        self.clicked_point_mode = self.get_parameter("clicked_point_mode").get_parameter_value().string_value.lower()
        self.plan_on_startup = self.get_parameter("plan_on_startup").get_parameter_value().bool_value
        self.enable_interactive_markers = self.get_parameter("enable_interactive_markers").get_parameter_value().bool_value
        self.interactive_marker_namespace = (
            self.get_parameter("interactive_marker_namespace").get_parameter_value().string_value
        )
        self.snap_search_radius_cells = (
            self.get_parameter("snap_search_radius_cells").get_parameter_value().integer_value
        )
        self.snap_to_traversable_layer = (
            self.get_parameter("snap_to_traversable_layer").get_parameter_value().bool_value
        )
        self.plan_on_marker_release = (
            self.get_parameter("plan_on_marker_release").get_parameter_value().bool_value
        )

        if self.clicked_point_mode not in ("alternate", "start", "goal"):
            raise ValueError("clicked_point_mode must be one of: alternate, start, goal")

        self.path_pub = self.create_publisher(Path, self.path_topic, qos)
        self.start_point_pub = self.create_publisher(PointStamped, "/pct_planner/start_point", qos)
        self.goal_point_pub = self.create_publisher(PointStamped, "/pct_planner/goal_point", qos)
        self.waypoint_marker_pub = self.create_publisher(MarkerArray, "/pct_planner/waypoint_markers", qos)
        self.planner = TomogramPlanner(self.cfg, self.rsg_root)
        self.get_logger().info(f"Loading tomogram: {self.tomo_file}")
        self.planner.loadTomogram(self.tomo_file)

        self.start_pose = None
        self.goal_pose = None
        self.start_layer = None
        self.goal_layer = None
        self.clicked_next_is_start = True
        self.marker_server = None

        self.create_subscription(PoseWithCovarianceStamped, self.start_topic, self.start_pose_cb, 10)
        self.create_subscription(PoseStamped, self.goal_topic, self.goal_pose_cb, 10)
        self.create_subscription(PointStamped, self.clicked_point_topic, self.clicked_point_cb, 10)

        if self.enable_interactive_markers:
            self.init_interactive_markers()

        self.get_logger().info(
            "Interactive marker planning ready. Drag Start and Goal in RViz "
            f"on {self.interactive_marker_namespace}/update. Compatibility "
            f"inputs remain enabled: {self.start_topic}, {self.goal_topic}, "
            f"{self.clicked_point_topic}."
        )

        if self.plan_on_startup:
            if self.start_pose is None:
                self.set_start(*self.start_pos, plan=False, update_marker=True)
            if self.goal_pose is None:
                self.set_goal(*self.end_pos, plan=False, update_marker=True)
            self.plan_current_waypoints()
    
    def configure_scene(self, scene_name):
        if scene_name == 'Spiral':
            self.tomo_file = 'spiral0.3_2'
            self.start_pos = np.array([-16.0, -6.0, 0.0], dtype=np.float32)
            self.end_pos = np.array([-26.0, -5.0, 0.0], dtype=np.float32)
        elif scene_name == 'Building':
            self.tomo_file = 'building2_9'
            self.start_pos = np.array([5.0, 5.0, 0.0], dtype=np.float32)
            self.end_pos = np.array([-6.0, -1.0, 0.0], dtype=np.float32)
        elif scene_name == 'Plaza':
            self.tomo_file = 'plaza3_10'
            self.start_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            self.end_pos = np.array([23.0, 10.0, 0.0], dtype=np.float32)
        elif scene_name == 'Rmuc':
            self.tomo_file = 'rmuc_2024'

            # rmuc_2024 的 tomography 日志：
            # Map center: [-6.81, -3.38]
            # Dim_x: 301, Dim_y: 331, resolution: 0.10
            # 估算地图范围大约：
            # x: -21.86 ~ 8.24
            # y: -19.93 ~ 13.17
            #
            # 这里先给一组保守的初始点，后续你可以在 RViz 里拖 marker。
            self.start_pos = np.array([-6.0, -4.0, 0.0], dtype=np.float32)
            self.end_pos = np.array([-2.0, -4.0, 0.0], dtype=np.float32)
        
        
        
        else:
            self.get_logger().error(f"Invalid scene name: {scene_name}")
            raise ValueError(f"Invalid scene name: {scene_name}")

    def start_pose_cb(self, msg):
        pose = msg.pose.pose
        self.set_start(pose.position.x, pose.position.y, pose.position.z)

    def goal_pose_cb(self, msg):
        pose = msg.pose
        self.set_goal(pose.position.x, pose.position.y, pose.position.z)

    def clicked_point_cb(self, msg):
        point = msg.point
        if self.clicked_point_mode == "start":
            self.set_start(point.x, point.y, point.z)
        elif self.clicked_point_mode == "goal":
            self.set_goal(point.x, point.y, point.z)
        elif self.clicked_next_is_start:
            self.set_start(point.x, point.y, point.z)
            self.clicked_next_is_start = False
        else:
            self.set_goal(point.x, point.y, point.z)
            self.clicked_next_is_start = True

    def set_start(self, x, y, z, plan=True, update_marker=True):
        waypoint_data = self.prepare_waypoint("start", x, y, z)
        if waypoint_data is None:
            if update_marker and self.start_pose is not None:
                self.update_interactive_marker_pose("start", self.start_pose)
            return False
        waypoint, layer = waypoint_data
        self.start_pose = waypoint
        self.start_layer = layer
        self.publish_waypoint(self.start_point_pub, self.start_pose)
        self.publish_waypoint_markers()
        if update_marker:
            self.update_interactive_marker_pose("start", self.start_pose)
        self.get_logger().info(f"Start set: {self.describe_pose(self.start_pose, self.start_layer)}")
        if plan:
            self.plan_current_waypoints()
        return True

    def set_goal(self, x, y, z, plan=True, update_marker=True):
        waypoint_data = self.prepare_waypoint("goal", x, y, z)
        if waypoint_data is None:
            if update_marker and self.goal_pose is not None:
                self.update_interactive_marker_pose("goal", self.goal_pose)
            return False
        waypoint, layer = waypoint_data
        self.goal_pose = waypoint
        self.goal_layer = layer
        self.publish_waypoint(self.goal_point_pub, self.goal_pose)
        self.publish_waypoint_markers()
        if update_marker:
            self.update_interactive_marker_pose("goal", self.goal_pose)
        self.get_logger().info(f"Goal set: {self.describe_pose(self.goal_pose, self.goal_layer)}")
        if plan:
            self.plan_current_waypoints()
        return True

    def prepare_waypoint(self, name, x, y, z):
        waypoint = np.array([x, y, z], dtype=np.float32)
        if not self.snap_to_traversable_layer:
            layer = self.planner.z2layer(waypoint[2], self.planner.pos2idx(waypoint[:2]))
            return waypoint, layer

        snapped = self.planner.snap_to_traversable(
            waypoint,
            radius_cells=self.snap_search_radius_cells,
        )
        if snapped is None:
            self.get_logger().warn(
                f"No traversable tomogram cell found near {name} "
                f"xyz=({waypoint[0]:.2f}, {waypoint[1]:.2f}, {waypoint[2]:.2f}); "
                "keeping the previous waypoint and skipping planning."
            )
            return None

        snapped_pose, snapped_idx, distance = snapped
        layer = int(snapped_idx[0])
        self.get_logger().info(
            f"{name.capitalize()} snapped to layer={layer}, "
            f"planner_y={snapped_idx[1]}, planner_x={snapped_idx[2]}, "
            f"distance={distance:.2f} m"
        )
        return snapped_pose, layer

    def plan_current_waypoints(self):
        if self.start_pose is None or self.goal_pose is None:
            return

        start_info = self.planner.cell_info(self.start_pose, self.start_layer)
        goal_info = self.planner.cell_info(self.goal_pose, self.goal_layer)
        self.get_logger().info(
            f"Planning from {self.describe_pose(self.start_pose, self.start_layer)} "
            f"to {self.describe_pose(self.goal_pose, self.goal_layer)}"
        )
        self.get_logger().info(
            f"Start cell: {self.format_cell_info(start_info)} | "
            f"Goal cell: {self.format_cell_info(goal_info)}"
        )
        try:
            traj_3d = self.planner.plan(
                self.start_pose,
                self.goal_pose,
                start_layer=self.start_layer,
                end_layer=self.goal_layer,
            )
        except ValueError as exc:
            self.get_logger().warn(f"Invalid waypoint: {exc}")
            return
        
        if traj_3d is not None:
            self.path_pub.publish(traj2ros(traj_3d))
            self.get_logger().info(f"Trajectory published on {self.path_topic}")
        else:
            self.get_logger().warn("Failed to generate trajectory")

    def publish_waypoint(self, publisher, waypoint):
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.point.x = float(waypoint[0])
        msg.point.y = float(waypoint[1])
        msg.point.z = float(waypoint[2])
        publisher.publish(msg)

    def publish_waypoint_markers(self):
        marker_array = MarkerArray()
        if self.start_pose is not None:
            marker_array.markers.append(
                self.make_waypoint_marker("start", self.start_pose, 0, (0.1, 0.8, 0.1, 1.0))
            )
        if self.goal_pose is not None:
            marker_array.markers.append(
                self.make_waypoint_marker("goal", self.goal_pose, 1, (0.9, 0.1, 0.1, 1.0))
            )
        self.waypoint_marker_pub.publish(marker_array)

    def make_waypoint_marker(self, name, waypoint, marker_id, color):
        marker = Marker()
        marker.header.frame_id = "map"
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "pct_waypoints"
        marker.id = marker_id
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        marker.pose.position.x = float(waypoint[0])
        marker.pose.position.y = float(waypoint[1])
        marker.pose.position.z = float(waypoint[2])
        marker.pose.orientation.w = 1.0
        marker.scale.x = 0.8
        marker.scale.y = 0.8
        marker.scale.z = 0.8
        marker.color.r = color[0]
        marker.color.g = color[1]
        marker.color.b = color[2]
        marker.color.a = color[3]
        marker.text = name
        return marker

    def init_interactive_markers(self):
        self.marker_server = InteractiveMarkerServer(self, self.interactive_marker_namespace)

        start = self.planner.snap_to_traversable(
            self.start_pos,
            radius_cells=max(self.snap_search_radius_cells, 10),
        )
        goal = self.planner.snap_to_traversable(
            self.end_pos,
            radius_cells=max(self.snap_search_radius_cells, 10),
        )
        self.start_pose = start[0] if start is not None else self.start_pos.copy()
        self.goal_pose = goal[0] if goal is not None else self.end_pos.copy()
        self.start_layer = int(start[1][0]) if start is not None else self.planner.z2layer(
            self.start_pose[2], self.planner.pos2idx(self.start_pose[:2])
        )
        self.goal_layer = int(goal[1][0]) if goal is not None else self.planner.z2layer(
            self.goal_pose[2], self.planner.pos2idx(self.goal_pose[:2])
        )

        self.marker_server.insert(
            self.make_interactive_marker("start", "Start", self.start_pose, (0.1, 0.8, 0.1, 1.0)),
            feedback_callback=self.interactive_marker_cb,
        )
        self.marker_server.insert(
            self.make_interactive_marker("goal", "Goal", self.goal_pose, (0.9, 0.1, 0.1, 1.0)),
            feedback_callback=self.interactive_marker_cb,
        )
        self.marker_server.applyChanges()
        self.publish_waypoint(self.start_point_pub, self.start_pose)
        self.publish_waypoint(self.goal_point_pub, self.goal_pose)
        self.publish_waypoint_markers()

    def make_interactive_marker(self, name, description, waypoint, color):
        marker = InteractiveMarker()
        marker.header.frame_id = "map"
        marker.name = name
        marker.description = description
        marker.pose.position.x = float(waypoint[0])
        marker.pose.position.y = float(waypoint[1])
        marker.pose.position.z = float(waypoint[2])
        marker.pose.orientation.w = 1.0
        marker.scale = 2.0

        drag_control = InteractiveMarkerControl()
        drag_control.name = f"{name}_drag"
        drag_control.description = f"Drag {description}"
        drag_control.orientation.w = 1.0
        drag_control.orientation_mode = InteractiveMarkerControl.VIEW_FACING
        drag_control.interaction_mode = InteractiveMarkerControl.MOVE_PLANE
        drag_control.independent_marker_orientation = True
        drag_control.always_visible = True
        drag_control.markers.append(self.make_sphere_marker(color))
        marker.controls.append(drag_control)

        marker.controls.append(self.make_move_axis_control("move_x", 1.0, 0.0, 0.0))
        marker.controls.append(self.make_move_axis_control("move_y", 0.0, 0.0, 1.0))
        marker.controls.append(self.make_move_axis_control("move_z", 0.0, 1.0, 0.0))
        marker.controls.append(self.make_xy_plane_control())
        return marker

    def make_sphere_marker(self, color):
        marker = Marker()
        marker.type = Marker.SPHERE
        marker.scale.x = 0.8
        marker.scale.y = 0.8
        marker.scale.z = 0.8
        marker.color.r = color[0]
        marker.color.g = color[1]
        marker.color.b = color[2]
        marker.color.a = color[3]
        return marker

    def make_move_axis_control(self, name, x, y, z):
        control = InteractiveMarkerControl()
        control.name = name
        control.orientation.w = 1.0
        control.orientation.x = x
        control.orientation.y = y
        control.orientation.z = z
        control.orientation_mode = InteractiveMarkerControl.FIXED
        control.interaction_mode = InteractiveMarkerControl.MOVE_AXIS
        control.description = name
        return control

    def make_xy_plane_control(self):
        control = InteractiveMarkerControl()
        control.name = "move_xy"
        control.orientation.w = 1.0
        control.orientation.y = 1.0
        control.orientation_mode = InteractiveMarkerControl.FIXED
        control.interaction_mode = InteractiveMarkerControl.MOVE_PLANE
        control.description = "move_xy"
        return control

    def interactive_marker_cb(self, feedback):
        if feedback.marker_name not in ("start", "goal"):
            return
        if feedback.event_type != InteractiveMarkerFeedback.MOUSE_UP:
            return

        pose = feedback.pose.position
        should_plan = self.plan_on_marker_release
        if feedback.marker_name == "start":
            self.set_start(pose.x, pose.y, pose.z, plan=should_plan, update_marker=True)
        else:
            self.set_goal(pose.x, pose.y, pose.z, plan=should_plan, update_marker=True)

    def update_interactive_marker_pose(self, name, waypoint):
        if self.marker_server is None:
            return
        pose = Pose()
        pose.position.x = float(waypoint[0])
        pose.position.y = float(waypoint[1])
        pose.position.z = float(waypoint[2])
        pose.orientation.w = 1.0
        self.marker_server.setPose(name, pose)
        self.marker_server.applyChanges()

    def destroy_node(self):
        if self.marker_server is not None:
            self.marker_server.shutdown()
            self.marker_server = None
        super().destroy_node()

    def describe_pose(self, pose, layer=None):
        info = self.planner.cell_info(pose, layer)
        layer = info["layer"]
        height = info.get("height", self.planner.layer_to_height(layer, info["planner_xy"]))
        return (
            f"xyz=({pose[0]:.2f}, {pose[1]:.2f}, {pose[2]:.2f}), "
            f"layer={layer}, layer_height={height:.2f}"
        )

    def format_cell_info(self, info):
        planner_xy = info["planner_xy"]
        grid_xy = info["grid_xy"]
        if not info["in_bounds"]:
            return (
                f"layer={info['layer']}, planner_yx=({planner_xy[0]}, {planner_xy[1]}), "
                f"grid_xy=({grid_xy[0]}, {grid_xy[1]}), out_of_bounds"
            )
        return (
            f"layer={info['layer']}, planner_yx=({planner_xy[0]}, {planner_xy[1]}), "
            f"grid_xy=({grid_xy[0]}, {grid_xy[1]}), valid={info['valid']}, "
            f"cost={info['cost']:.2f}, height={info['height']:.2f}"
        )


def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = PCTPlanner()
        rclpy.spin(node)
    except ValueError as e:
        print(f"Error initializing node: {e}")
    except KeyboardInterrupt:
        pass
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
