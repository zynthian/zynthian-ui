cmake_minimum_required(VERSION 3.0)
# set(CMAKE_VERBOSE_MAKEFILE ON)

project(zynaudioplayer)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynaudioplayer SHARED player.c tinyosc.c)
	target_link_libraries(zynaudioplayer jack sndfile pthread samplerate)

install(TARGETS zynaudioplayer LIBRARY DESTINATION lib)
