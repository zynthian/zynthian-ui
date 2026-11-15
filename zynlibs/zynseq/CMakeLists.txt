cmake_minimum_required(VERSION 3.20)
project(zynseq)

include(CheckIncludeFiles)
include(CheckLibraryExists)

# mimalloc is disabled by default: linked into this library (loaded by Python with ctypes), it replaces
# new/delete only partially. When libstdc++ was already loaded by another library (e.g. libzyncore),
# libstdc++ keeps the glibc allocator while code inlined in zynseq uses mimalloc => memory allocated
# by one is freed by the other => segfault (e.g. mi_free in getState/json::dump with Release builds).
# TODO: proper RT-safe memory management for the jack process (explicit mimalloc heap/STL allocator
# or preallocated pools) instead of a global allocator override.
option(ZYNSEQ_USE_MIMALLOC "Link zynseq with mimalloc (unsafe as global override, see above)" OFF)
if(ZYNSEQ_USE_MIMALLOC)
    find_package(mimalloc QUIET)
endif()

link_directories(/usr/local/lib)

add_library(zynseq SHARED zynseq.h zynseq.cpp sequencemanager.cpp pattern.cpp sequence.cpp timebase.cpp track.cpp)
add_definitions(-Werror)
target_compile_options(zynseq PRIVATE -Wmisleading-indentation)

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
