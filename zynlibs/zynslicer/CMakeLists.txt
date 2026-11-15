cmake_minimum_required(VERSION 3.20)
project(zynslicer)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynslicer SHARED slicer.c)
add_definitions(-Werror)
target_compile_options(zynslicer PRIVATE -Wmisleading-indentation)
target_link_libraries(zynslicer jack sndfile samplerate m)

install(TARGETS zynslicer LIBRARY DESTINATION lib)
