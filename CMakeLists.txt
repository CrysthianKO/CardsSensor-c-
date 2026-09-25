cmake_minimum_required(VERSION 3.22)
project(CardsSensor)

## OpenCV 5.0 requires C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

## Locate the pre-built OpenCV installation. If CMake cannot find it
## automatically, pass the path explicitly:
##   cmake -DOpenCV_DIR=/absolute/path/to/opencv/build/ ..
find_package(OpenCV 4.6 REQUIRED)

message(STATUS "Found OpenCV version: ${OpenCV_VERSION}")
message(STATUS "OpenCV include directories: ${OpenCV_INCLUDE_DIRS}")

add_executable(scanner main.cpp)
target_link_libraries(scanner PRIVATE ${OpenCV_LIBS})
