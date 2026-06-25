cmake_minimum_required(VERSION 3.20)
project(zynseq)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)
set (CMAKE_BUILD_TYPE Debug)

add_library(zynseq SHARED zynseq.h zynseq.cpp sequencemanager.cpp pattern.cpp sequence.cpp timebase.cpp track.cpp)
add_definitions(-Werror)
target_link_libraries(zynseq jack)

install(TARGETS zynseq LIBRARY DESTINATION lib)
