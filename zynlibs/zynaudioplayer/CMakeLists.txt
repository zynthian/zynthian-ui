cmake_minimum_required(VERSION 3.0)
# set(CMAKE_VERBOSE_MAKEFILE ON)

project(zynaudioplayer)

option(ENABLE_OSC "Enable OSC support" TRUE)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

if(ENABLE_OSC)
	message("OSC enabled")
	add_definitions(-DENABLE_OSC)
	add_library(zynaudioplayer SHARED player.cpp tinyosc.c)
		target_link_libraries(zynaudioplayer jack sndfile pthread samplerate rubberband)
else()
	message("OSC disabled")
	add_library(zynaudioplayer SHARED player.cpp)
		target_link_libraries(zynaudioplayer jack sndfile pthread samplerate rubberband)
endif()

install(TARGETS zynaudioplayer LIBRARY DESTINATION lib)
