cmake_minimum_required(VERSION 3.20)
project(zynseq LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find dependencies (mimalloc is no longer REQUIRED)
find_package(mimalloc QUIET)
find_package(PkgConfig REQUIRED)
pkg_check_modules(JACK REQUIRED IMPORTED_TARGET jack)

# Define the library
add_library(zynseq SHARED
    zynseq.h
    zynseq.cpp
    sequencemanager.cpp
    pattern.cpp
    sequence.cpp
    timebase.cpp
    track.cpp
)

# Base compiler options
#target_compile_options(zynseq PRIVATE -Werror -Wall -Wextra)
target_compile_options(zynseq PRIVATE -Werror)

# Base library links
target_link_libraries(zynseq PRIVATE PkgConfig::JACK)

# Conditional mimalloc linking
if(mimalloc_FOUND)
    target_link_libraries(zynseq PRIVATE mimalloc)
    # Defines HAS_MIMALLOC so you can use #ifdef HAS_MIMALLOC in your C++ code
    target_compile_definitions(zynseq PRIVATE HAS_MIMALLOC)
    message(STATUS "mimalloc found and enabled for zynseq")
else()
    message(STATUS "mimalloc NOT found; falling back to default system allocator")
endif()

# Installation
include(GNUInstallDirs)
install(TARGETS zynseq LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR})

