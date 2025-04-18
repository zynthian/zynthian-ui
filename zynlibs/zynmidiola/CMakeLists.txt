cmake_minimum_required(VERSION 3.0)
# set(CMAKE_VERBOSE_MAKEFILE ON)

project(zynmidiola)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_executable(zynmidiola midiola.cpp)
add_definitions(-Werror)
target_link_libraries(zynmidiola jack ola olacommon protobuf)

