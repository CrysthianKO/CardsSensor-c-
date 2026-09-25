#!/bin/bash

BUILD_DIR="build"
PROJECT_NAME="scanner"

if [ ! -d "$BUILD_DIR" ]; then
    echo "Build directory not found. Configuring project..."
    mkdir "$BUILD_DIR"
    cmake -B "$BUILD_DIR" -S .
fi

echo "Building project (will only recompile changed files)..."

cmake --build "$BUILD_DIR"

$BUILD_DIR/$PROJECT_NAME
