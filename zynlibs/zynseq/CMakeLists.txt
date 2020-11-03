cmake_minimum_required(VERSION 2.6)
project(zynseq)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynseq SHARED zynseq.h zynseq.cpp pattern.cpp song.cpp patternmanager.cpp sequence.cpp timebase.cpp)
	target_link_libraries(zynseq jack)

install(TARGETS zynseq LIBRARY DESTINATION lib)
