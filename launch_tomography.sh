#!/usr/bin/env bash
set -e

ROOT_DIR=$(cd $(dirname "${BASH_SOURCE[0]}"); pwd -P)

source /opt/ros/humble/setup.bash
source $ROOT_DIR/.venv/bin/activate

export PCT_ROOT=$ROOT_DIR
export LD_LIBRARY_PATH=$PCT_ROOT/cJSON-1.7.19/lib:$PCT_ROOT/gtsam-4.2/lib:$PCT_ROOT/osqp-1.0.0/lib:$PCT_ROOT/pcl-1.15.1/lib:$LD_LIBRARY_PATH

source $ROOT_DIR/install/setup.bash

export PYTHONPATH=$PYTHONPATH:$ROOT_DIR/.venv/lib/python$(cat $ROOT_DIR/.python-version)/site-packages

ros2 launch tomography tomography.launch.py "$@"
