#!/bin/bash
# Build the real libzyncore.so for the `native` tests: wiring layout TOUCH_ONLY, i.e. the real
# ZynMidiRouter + ZynMaster, without wiringPi / I2C / rotaries. Needs cmake, gcc, libjack-dev, liblo-dev.
# Builds out of tree, so the zyncoder checkout (and its own build/ dir) is left untouched.
#
#   tests/native/build_zyncore.sh [path/to/zyncoder]     (default: ../zyncoder next to zynthian-ui)
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:-${ZYNCODER_DIR:-$HERE/../../../zyncoder}}"
SRC="$(cd "$SRC" && pwd)"
BUILD="$HERE/build"
mkdir -p "$BUILD"
cd "$BUILD"
ZYNTHIAN_WIRING_LAYOUT=TOUCH_ONLY TPA6130_KERNEL_DRIVER_LOADED=1 cmake "$SRC" > cmake.log 2>&1 \
    || { cat cmake.log; exit 1; }
make zyncore 2>&1 | tail -3
echo "Built $BUILD/libzyncore.so from $SRC"
