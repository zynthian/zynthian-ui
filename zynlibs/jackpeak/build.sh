#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

pushd $DIR
	if [ ! -d build ]; then
		mkdir build
	fi
	pushd build
		cmake ..
		make
	popd
popd
