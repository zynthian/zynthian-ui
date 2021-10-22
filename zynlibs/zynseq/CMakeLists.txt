cmake_minimum_required(VERSION 3.0)
project(zynseq)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynseq SHARED zynseq.h zynseq.cpp sequencemanager.cpp pattern.cpp sequence.cpp timebase.cpp track.cpp)
	target_link_libraries(zynseq jack)

install(TARGETS zynseq LIBRARY DESTINATION lib)
