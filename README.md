# PCT_planner ROS2 Humble 部署指南

## 1. 当前验证环境

本文档基于以下设备与软件环境完成部署验证：

```bash
Ubuntu 22.04
ROS2 Humble
Python 3.10
CUDA 可用，CuPy 检测到 cuda device count = 1
Open3D 0.19.0
CuPy 14.0.1 / cupy-cuda13x
项目路径：~/PCT_planner  注意一定要放在主目录下，否则有一些硬编码的地方会报错
```

本次没有采用 conda。最终采用的是：

```text
系统 ROS2 Humble
+ 项目内 Python venv
+ 项目目录内独立编译第三方 C++ 库
```

这样做的原因是：ROS2 Humble 与系统 Python、`rclpy`、`ament`、`colcon`、消息包生成环境绑定较深，使用 conda 容易影响其他 ROS2 功能包。因此最终只隔离 Python 依赖，而不替换系统 ROS2 环境。

---

## 2. 项目最终目录结构

部署完成后，项目根目录结构大致如下：

```bash
~/PCT_planner
├── .venv
├── build
├── install
├── log
├── cJSON-1.7.19
├── gtsam-4.2
├── osqp-1.0.0
├── pcl-1.15.1
├── src
│   ├── cJSON-1.7.19
│   ├── gtsam-4.2
│   ├── osqp-1.0.0
│   └── pcl-1.15.1
├── pct_planner
├── tomography
├── tomogram_rsc
├── build_3rdparty.sh
├── launch_tomography.sh
└── launch_pct_planner_node.sh
```

其中：

```text
src/                 存放第三方库源码
cJSON-1.7.19/         cJSON 安装结果
gtsam-4.2/            GTSAM 安装结果
osqp-1.0.0/           OSQP 安装结果
pcl-1.15.1/           PCL 安装结果
.venv/                项目私有 Python 环境
tomogram_rsc/pcd/     点云资源
tomogram_rsc/tomogram/生成的 tomogram pickle
```

---

## 3. 安装系统依赖

```bash
sudo apt update

sudo apt install -y \
  git wget unzip curl \
  build-essential cmake ninja-build pkg-config ccache \
  python3 python3-pip python3-venv python3-dev \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool \
  libeigen3-dev \
  libboost-all-dev \
  libtbb-dev \
  libflann-dev \
  libqhull-dev \
  libusb-1.0-0-dev \
  libgtest-dev \
  ros-humble-rviz2 \
  ros-humble-rclpy \
  ros-humble-ament-cmake \
  ros-humble-ament-cmake-python \
  ros-humble-launch \
  ros-humble-launch-ros \
  ros-humble-nav-msgs \
  ros-humble-sensor-msgs \
  ros-humble-sensor-msgs-py \
  ros-humble-geometry-msgs \
  ros-humble-std-msgs \
  ros-humble-visualization-msgs \
  ros-humble-pybind11-vendor \
  pybind11-dev
```
# 安装可视化拖动工具maker
```
sudo apt install ros-humble-rviz2 ros-humble-interactive-markers
```
初始化 rosdep：

```bash
sudo rosdep init 2>/dev/null || true
rosdep update
```

---

## 4. 创建 Python venv

cd ~
git clone -b feat/ros2pkg https://github.com/2473o/PCT_planner.git
cd ~/PCT_planner

进入项目根目录：

```bash
cd ~/PCT_planner
source /opt/ros/humble/setup.bash

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install numpy scipy matplotlib pyyaml open3d
python -m pip install catkin_pkg lark empy==3.3.4 pybind11
```

安装 CuPy。当前验证环境使用的是：

```bash
python -m pip install cupy-cuda13x
```

如果你的 CUDA 是 12.x，可尝试：

```bash
python -m pip install cupy-cuda12x
```

如果 CUDA 是 11.x，可尝试：

```bash
python -m pip install cupy-cuda11x
```

验证 Python/GPU 依赖：

```bash
python - <<'PY'
import cupy as cp
import open3d as o3d
import numpy as np
import yaml

print("cupy:", cp.__version__)
print("open3d:", o3d.__version__)
print("numpy:", np.__version__)
print("cuda device count:", cp.cuda.runtime.getDeviceCount())
PY
```

正常情况下应能看到：

```text
cuda device count: 1
```

创建 `.python-version`：

```bash
cd ~/PCT_planner
python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" > .python-version
cat .python-version
```

通常输出：

```text
3.10
```

---



## 5. 下载第三方库源码，本代码已经默认自带了

```bash


cd ~/PCT_planner
mkdir -p src
cd src

git clone -b v1.7.19 https://github.com/DaveGamble/cJSON.git cJSON-1.7.19
git clone -b 4.2 https://github.com/borglab/gtsam.git gtsam-4.2
git clone -b v1.0.0 https://github.com/osqp/osqp.git osqp-1.0.0
git clone -b pcl-1.15.1 https://github.com/PointCloudLibrary/pcl.git pcl-1.15.1
```

检查：

```bash
ls ~/PCT_planner/src
```

应看到：

```text
cJSON-1.7.19
gtsam-4.2
osqp-1.0.0
pcl-1.15.1
```

---

## 6. 修改并编译第三方库
建议分开编译，便于定位错误：

```bash
cd ~/PCT_planner
source /opt/ros/humble/setup.bash
source .venv/bin/activate

./build_3rdparty.sh cjson
./build_3rdparty.sh osqp
./build_3rdparty.sh gtsam
./build_3rdparty.sh pcl
```

编译完成后，项目根目录应出现：

```bash
~/PCT_planner/cJSON-1.7.19
~/PCT_planner/osqp-1.0.0
~/PCT_planner/gtsam-4.2
~/PCT_planner/pcl-1.15.1
```

---

## 7. 防止 colcon 扫描第三方库

第三方库已经通过 `build_3rdparty.sh` 编译，不应再被 `colcon build` 当作 ROS2 包扫描。因此需要添加 `COLCON_IGNORE`：

```bash
cd ~/PCT_planner

touch cJSON-1.7.19/COLCON_IGNORE
touch gtsam-4.2/COLCON_IGNORE
touch osqp-1.0.0/COLCON_IGNORE
touch pcl-1.15.1/COLCON_IGNORE

touch src/cJSON-1.7.19/COLCON_IGNORE
touch src/gtsam-4.2/COLCON_IGNORE
touch src/osqp-1.0.0/COLCON_IGNORE
touch src/pcl-1.15.1/COLCON_IGNORE
```

检查：

```bash
colcon list
```

理想情况下只看到：

```text
pct_planner
tomogram_rsc
tomography
```

---


## 11. 编译整个 ROS2 工作空间

每次新终端编译前，建议先设置路径：

```bash
cd ~/PCT_planner

source /opt/ros/humble/setup.bash
source .venv/bin/activate

export PCT_ROOT=$HOME/PCT_planner

export cJSON_DIR=$PCT_ROOT/cJSON-1.7.19/lib/cmake/cJSON
export GTSAM_DIR=$PCT_ROOT/gtsam-4.2/lib/cmake/GTSAM
export OSQP_DIR=$PCT_ROOT/osqp-1.0.0/lib/cmake/osqp

export PCL_ROOT=$PCT_ROOT/pcl-1.15.1
export PCL_DIR=$PCL_ROOT/share/pcl-1.15

export pybind11_DIR=$(python -c "import pybind11; print(pybind11.get_cmake_dir())")

export CMAKE_PREFIX_PATH=$cJSON_DIR:$GTSAM_DIR:$OSQP_DIR:$PCL_DIR:$pybind11_DIR:$CMAKE_PREFIX_PATH
export LD_LIBRARY_PATH=$PCT_ROOT/cJSON-1.7.19/lib:$PCT_ROOT/gtsam-4.2/lib:$PCT_ROOT/osqp-1.0.0/lib:$PCT_ROOT/pcl-1.15.1/lib:$LD_LIBRARY_PATH
```

完整编译：

```bash
rm -rf build install log

colcon build --symlink-install --cmake-args \
  -DCMAKE_BUILD_TYPE=Release \
  -Dpybind11_DIR=$pybind11_DIR

source install/setup.bash
```

检查 ROS2 包：

```bash
ros2 pkg list | grep -E "pct_planner|tomography|tomogram_rsc"
```

应看到：

```text
pct_planner
tomogram_rsc
tomography
```

---


## 13. 生成 tomogram

以 Plaza 场景为例：

```bash
cd ~/PCT_planner
./launch_tomography.sh scene_name:=plaza
```

```bash
cd ~/PCT_planner
./launch_tomography.sh scene_name:=building
```

```bash
cd ~/PCT_planner
./launch_tomography.sh scene_name:=rmuc
```


成功后检查：

```bash
find ~/PCT_planner -name "*.pickle"
```

本次验证中成功生成：

```bash
/home/xiaoqi_wen/PCT_planner/install/tomogram_rsc/share/tomogram_rsc/tomogram/plaza3_10.pickle
```
# 注意，但是不要关闭这个rviz2的可视化，因为后面的路径发布还要用到
---

## 14. 运行 planner

```bash
cd ~/PCT_planner
./launch_pct_planner_node.sh scene_name:=Plaza
```


```bash
cd ~/PCT_planner
./launch_pct_planner_node.sh scene_name:=Building
```


```bash
cd ~/PCT_planner
./launch_pct_planner_node.sh scene_name:=Rmuc
```

注意大小写：

```text
tomography 使用：scene_name:=plaza
planner 使用：scene_name:=Plaza
```

成功日志应类似：

```text
Using scene: Plaza
Loading tomogram: plaza3_10
Planning from [0. 0.] to [23. 10.]
path found
Optimization finished.
Trajectory published
```

本次验证中 planner 已成功完成 A* 搜索和轨迹优化，并发布 trajectory。

#v2.0版本完成了移除前面的硬编码部分，使得通过maker交互实现init和goal的选择和吸附

---

## 15. 最终验证话题

启动 planner 后，新开终端：

```bash
source /opt/ros/humble/setup.bash
source ~/PCT_planner/.venv/bin/activate
source ~/PCT_planner/install/setup.bash

ros2 topic list
```

查看路径消息：

```bash
ros2 topic echo /pct_path --once
```

如果能看到 `nav_msgs/msg/Path` 类型消息，则说明规划器输出正常。

---



## 16. 一键运行流程总结

首次部署完成后，日常运行只需要：

### 生成 tomogram

```bash
cd ~/PCT_planner
./launch_tomography.sh scene_name:=plaza
```

### 运行 planner

```bash
cd ~/PCT_planner
./launch_pct_planner_node.sh scene_name:=Plaza
```

### 验证输出

```bash
source /opt/ros/humble/setup.bash
source ~/PCT_planner/.venv/bin/activate
source ~/PCT_planner/install/setup.bash

ros2 topic list
ros2 topic echo /pct_path --once
```

---

## 17. 当前部署结论

当前设备上，PCT_planner 的 ROS2 Humble 版本已经完成部署验证：

```text
PCD 资源读取：成功
tomography 生成 tomogram：成功
plaza3_10.pickle：成功生成
planner 加载 tomogram：成功
A* 搜索：成功
GTSAM 轨迹优化：成功
trajectory 发布：成功
```

本项目后续如果接入自己的机器人导航系统，重点关注 planner 发布的路径话题，并将其转换或接入到已有控制器、Nav2 路径跟踪模块或自定义局部控制器中。

