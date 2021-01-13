cmake_minimum_required(VERSION 2.6)
project(zynsmf)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynsmf SHARED zynsmf.h zynsmf.cpp)
	target_link_libraries(zynsmf)

install(TARGETS zynsmf LIBRARY DESTINATION lib)
