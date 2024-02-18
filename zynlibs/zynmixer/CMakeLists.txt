cmake_minimum_required(VERSION 3.0)
project(zynmixer)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynmixer SHARED mixer.h mixer.c tinyosc.h tinyosc.c)
add_definitions(-Werror)
target_link_libraries(zynmixer jack)

install(TARGETS zynmixer LIBRARY DESTINATION lib)
