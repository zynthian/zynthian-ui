#!/bin/bash
# Build the real native libraries used by the `native` tests, out of tree into tests/native/build/:
#
#   libzyncore.so          zyncoder, wiring layout TOUCH_ONLY: the real ZynMidiRouter + ZynMaster without
#                          wiringPi / I2C / rotaries / switches (needs the separate zyncoder repo);
#                          built by build_zyncore.sh, which can also be run on its own
#   libzynseq.so, libzynsmf.so, libzynaudioplayer.so, libzynmixer*.so     from zynlibs/
#
# Needs cmake, gcc/g++, libjack-dev, liblo-dev, nlohmann-json3-dev (zynseq) (+ libsndfile, libsamplerate,
# librubberband dev for the audio player). The source trees (and their own build/ dirs) are left untouched.
#
#   tests/native/build_native.sh [path/to/zyncoder]     (default: ../zyncoder next to zynthian-ui)
#   ONLY="zynseq zynsmf" tests/native/build_native.sh   build just some components
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI="$(cd "$HERE/../.." && pwd)"
ZYNCODER="${1:-${ZYNCODER_DIR:-$UI/../zyncoder}}"
BUILD="$HERE/build"
ONLY="${ONLY:-zyncore zynseq zynsmf zynaudioplayer zynmixer}"
mkdir -p "$BUILD"
failed=0

# The zynlibs are built Release, like their own build.sh does: without optimisation libzynaudioplayer has an
# undefined symbol (`inline` get_player() in player.c) and cannot be loaded.
# The CMakeLists use -Werror, which fails on distributions whose compiler is hardened (Ubuntu: _FORTIFY_SOURCE
# makes an ignored fread() result an error) although the code is fine. -Wno-error alone is not enough (the
# CMakeLists' later -Werror wins with some GCC versions), so the warning itself is switched off.
WARN="-Wno-error -Wno-unused-result"
RELEASE="-DCMAKE_BUILD_TYPE=Release"

build() {  # build <component> <source dir> <cmake args> <env assignments...>
    local name="$1" src="$2" cmake_args="$3"; shift 3
    [[ " $ONLY " == *" $name "* ]] || return 0
    if [ ! -f "$src/CMakeLists.txt" ]; then
        echo "SKIP  $name: no sources at $src"; return 0
    fi
    mkdir -p "$BUILD/$name"
    if ( cd "$BUILD/$name" && env "$@" cmake $cmake_args "$src" > cmake.log 2>&1 && make > make.log 2>&1 ); then
        cp "$BUILD/$name"/lib*.so "$BUILD/"
        echo "OK    $name"
    else
        echo "FAIL  $name (see $BUILD/$name/cmake.log, make.log)"; tail -15 "$BUILD/$name/make.log" 2>/dev/null
        failed=1
    fi
}

[ -d "$ZYNCODER" ] && ZYNCODER="$(cd "$ZYNCODER" && pwd)"
# libzyncore.so keeps its own script (build_zyncore.sh), which this one just calls
if [[ " $ONLY " == *" zyncore "* ]]; then
    if [ -f "$ZYNCODER/CMakeLists.txt" ]; then
        if "$HERE/build_zyncore.sh" "$ZYNCODER" > "$BUILD/zyncore.log" 2>&1; then
            echo "OK    zyncore"
        else
            echo "FAIL  zyncore (see $BUILD/zyncore.log)"; tail -15 "$BUILD/zyncore.log"; failed=1
        fi
    else
        echo "SKIP  zyncore: no sources at $ZYNCODER"
    fi
fi
build zynseq         "$UI/zynlibs/zynseq"          "$RELEASE" CXXFLAGS="${CXXFLAGS:-} $WARN" CFLAGS="${CFLAGS:-} $WARN"
build zynsmf         "$UI/zynlibs/zynsmf"          "$RELEASE" CXXFLAGS="${CXXFLAGS:-} $WARN" CFLAGS="${CFLAGS:-} $WARN"
build zynaudioplayer "$UI/zynlibs/zynaudioplayer"  "$RELEASE" CXXFLAGS="${CXXFLAGS:-} $WARN" CFLAGS="${CFLAGS:-} $WARN"
build zynmixer       "$UI/zynlibs/zynmixer"        "$RELEASE" CXXFLAGS="${CXXFLAGS:-} $WARN" CFLAGS="${CFLAGS:-} $WARN"
ls "$BUILD"/lib*.so
exit $failed
