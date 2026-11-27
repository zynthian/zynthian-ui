cmake_minimum_required(VERSION 3.20)
project(zynaudio2midi C)

include(CheckIncludeFiles)
include(CheckLibraryExists)

link_directories(/usr/local/lib)

add_library(zynaudio2midi SHARED audio2midi.h audio2midi.c a2m_dsp.h a2m_dsp.c)
add_definitions(-Werror)
set_property(TARGET zynaudio2midi PROPERTY C_STANDARD 11)
target_compile_options(zynaudio2midi PRIVATE -Wall -Wmisleading-indentation)
target_link_libraries(zynaudio2midi jack m)

install(TARGETS zynaudio2midi LIBRARY DESTINATION lib)
