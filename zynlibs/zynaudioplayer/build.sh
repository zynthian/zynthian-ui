#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

pushd $DIR
	if [ ! -d build ]; then
		mkdir build
	fi
	pushd build
		cmake -D CMAKE_CXX_FLAGS="-Wno-psabi" -D ENABLE_OSC=0 ..
		make
		success=$?
	popd
popd
exit $success
