cmake_minimum_required(VERSION 2.6)
# set(CMAKE_VERBOSE_MAKEFILE ON)

project(zynsmf)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynsmf SHARED zynsmf.cpp event.cpp track.cpp smf.cpp)
	target_link_libraries(zynsmf jack)

install(TARGETS zynsmf LIBRARY DESTINATION lib)
