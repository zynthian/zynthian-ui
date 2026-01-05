#!/bin/bash

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

$SCRIPT_PATH/zynsmf/build.sh
$SCRIPT_PATH/zynseq/build.sh
$SCRIPT_PATH/zynaudioplayer/build.sh
$SCRIPT_PATH/zynmixer/build.sh
$SCRIPT_PATH/zynclippy/build.sh

