cmake_minimum_required(VERSION 3.20)
# set(CMAKE_VERBOSE_MAKEFILE ON)

project(zynaudioplayer)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynaudioplayer SHARED player.c)
add_definitions(-Werror)
target_compile_options(zynaudioplayer PRIVATE -Wmisleading-indentation)
target_link_libraries(zynaudioplayer jack sndfile pthread samplerate rubberband)

install(TARGETS zynaudioplayer LIBRARY DESTINATION lib)