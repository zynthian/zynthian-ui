cmake_minimum_required(VERSION 3.20)
project(zynseq)

include(CheckIncludeFiles)
include(CheckLibraryExists)
find_package(mimalloc QUIET)

link_directories(/usr/local/lib)
set (CMAKE_BUILD_TYPE Debug)

add_library(zynseq SHARED zynseq.h zynseq.cpp sequencemanager.cpp pattern.cpp sequence.cpp timebase.cpp track.cpp)
add_definitions(-Werror)

if(mimalloc_FOUND)
    # Defines HAS_MIMALLOC so you can use #ifdef HAS_MIMALLOC in your C++ code
    target_compile_definitions(zynseq PRIVATE HAS_MIMALLOC)
    target_link_libraries(zynseq jack mimalloc)
    message(STATUS "mimalloc found and enabled for zynseq")
else()
    target_link_libraries(zynseq jack)
    message(STATUS "mimalloc NOT found; falling back to default system allocator")
endif()


install(TARGETS zynseq LIBRARY DESTINATION lib)
