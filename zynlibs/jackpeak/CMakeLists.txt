cmake_minimum_required(VERSION 3.0)
project(jackpeak)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(jackpeak SHARED jackpeak.h jackpeak.c)
	target_link_libraries(jackpeak jack)

install(TARGETS jackpeak LIBRARY DESTINATION ../lib)
