cmake_minimum_required(VERSION 3.20)
# set(CMAKE_VERBOSE_MAKEFILE ON)

project(zynaudioplayer)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynaudioplayer SHARED player.c)

option(ZYNAUDIOPLAYER_WERROR "Treat compiler warnings as errors" ON)
target_compile_options(zynaudioplayer PRIVATE -Wall)
if(ZYNAUDIOPLAYER_WERROR)
    target_compile_options(zynaudioplayer PRIVATE -Werror)
endif()

target_link_libraries(zynaudioplayer jack sndfile pthread samplerate rubberband)

install(TARGETS zynaudioplayer LIBRARY DESTINATION lib)