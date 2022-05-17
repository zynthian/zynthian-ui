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
	add_library(zynaudioplayer SHARED player.c tinyosc.c)
		target_link_libraries(zynaudioplayer jack sndfile pthread samplerate)
else()
	message("OSC disabled")
	add_library(zynaudioplayer SHARED player.c)
		target_link_libraries(zynaudioplayer jack sndfile pthread samplerate)
endif()

install(TARGETS zynaudioplayer LIBRARY DESTINATION lib)
