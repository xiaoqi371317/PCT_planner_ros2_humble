#!/usr/bin/env bash
set -e

ROOT_DIR=$(cd $(dirname "${BASH_SOURCE[0]}"); pwd)

cJSON_VERSION=1.7.19
gtsam_VERSION=4.2
osqp_VERSION=1.0.0
pcl_VERSION=1.15.1

export cJSON_DIR=$ROOT_DIR/cJSON-$cJSON_VERSION/lib/cmake/cJSON
export GTSAM_DIR=$ROOT_DIR/gtsam-$gtsam_VERSION/lib/cmake/GTSAM
export OSQP_DIR=$ROOT_DIR/osqp-$osqp_VERSION/lib/cmake/osqp

export PCL_ROOT=$ROOT_DIR/pcl-$pcl_VERSION
export PCL_DIR=$PCL_ROOT/share/pcl-1.15
export PCL_INCLUDE_DIRS=$PCL_ROOT/include/pcl-1.15

build_package(){
    package_name=$1
    package_version=$2
    shift 2
    cmake_args=("$@")

    SRC_DIR=$ROOT_DIR/src/$package_name-$package_version
    BUILD_DIR=$SRC_DIR/build
    INSTALL_DIR=$ROOT_DIR/$package_name-$package_version

    if [ ! -d "$SRC_DIR" ]; then
        echo "[ERROR] Source directory not found: $SRC_DIR"
        exit 1
    fi

    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"

    cd "$BUILD_DIR"

    cmake .. -GNinja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
        -DCMAKE_C_COMPILER_LAUNCHER=ccache \
        "${cmake_args[@]}"

    ninja -j2
    ninja install
}

build_cjson(){
    build_package "cJSON" "$cJSON_VERSION"
}

build_gtsam(){
    build_package "gtsam" "$gtsam_VERSION" \
        -DGTSAM_USE_SYSTEM_EIGEN=ON \
        -DGTSAM_BUILD_TESTS=OFF \
        -DGTSAM_BUILD_EXAMPLES_ALWAYS=OFF \
        -DGTSAM_BUILD_UNSTABLE=OFF
}

build_osqp(){
    build_package "osqp" "$osqp_VERSION"
}

build_pcl(){
    build_package "pcl" "$pcl_VERSION" \
        -DCMAKE_PREFIX_PATH="$ROOT_DIR/cJSON-$cJSON_VERSION" \
        -DBUILD_examples=OFF \
        -DBUILD_tools=OFF \
        -DBUILD_apps=OFF \
        -DBUILD_global_tests=OFF \
        -DBUILD_simulation=OFF \
        -DBUILD_surface=OFF \
        -DBUILD_registration=OFF \
        -DBUILD_stereo=OFF \
        -DBUILD_tracking=OFF
}

case "$1" in
    "cjson")
        build_cjson
        ;;
    "gtsam")
        build_gtsam
        ;;
    "osqp")
        build_osqp
        ;;
    "pcl")
        build_pcl
        ;;
    "all")
        build_cjson
        build_osqp
        build_gtsam
        build_pcl
        ;;
    *)
        echo "Usage: $0 {cjson|gtsam|osqp|pcl|all}"
        exit 1
        ;;
esac
