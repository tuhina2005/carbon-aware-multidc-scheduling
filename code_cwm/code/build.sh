#!/bin/bash

set -e

BUILD_DIR="build"
BUILD_TYPE="Release" 

if [ -d "$BUILD_DIR" ]; then
  rm -rf "$BUILD_DIR"
fi
mkdir "$BUILD_DIR"
cd "$BUILD_DIR"

cmake -G Ninja -DCMAKE_BUILD_TYPE="$BUILD_TYPE" ..
#cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer" ..

NCORES=4
unamestr=$(uname)
if [[ "$unamestr" == "Linux" ]]; then
    NCORES=$(grep -c ^processor /proc/cpuinfo)
elif [[ "$unamestr" == "Darwin" ]]; then
    NCORES=$(sysctl -n hw.ncpu)
fi
ninja -j"$NCORES"

cd ..
if [ -d "deploy" ]; then
  rm -rf deploy/
fi
mkdir deploy

cp build/main deploy/
cp build/heft_mapping deploy/
cp build/setup_for_CaWoSched deploy/
cp build/solve_cwm deploy/

rm -rf "$BUILD_DIR"
