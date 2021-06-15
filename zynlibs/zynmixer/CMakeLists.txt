cmake_minimum_required(VERSION 2.6)
project(zynmixer)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynmixer SHARED mixer.h mixer.c tinyosc.h tinyosc.c)
	target_link_libraries(zynmixer jack)

install(TARGETS zynmixer LIBRARY DESTINATION lib)
