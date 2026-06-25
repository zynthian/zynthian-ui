cmake_minimum_required(VERSION 3.20)
project(zynclippy)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynclippy SHARED clippy.c)
add_definitions(-Werror)
target_link_libraries(zynclippy jack sndfile samplerate rubberband)

install(TARGETS zynclippy LIBRARY DESTINATION lib)
