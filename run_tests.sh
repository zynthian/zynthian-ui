#!/bin/bash
# Test runner.
#
#   ./run_tests.sh            hermetic suite (no hardware / JACK / display needed)   <- default, same as CI
#   ./run_tests.sh gui        same, under xvfb so the Tk-based tests also run
#   ./run_tests.sh native     builds the real native libraries if needed (tests/native/build_native.sh) and runs
#                             tests/native: zyncore router, zynseq, ... on a private dummy jackd
#   ./run_tests.sh <pytest args...>   anything else is passed to pytest (e.g. -k controller -x)
#
# See tests/README.md

cd "$(dirname "$0")" || exit 1
[ -f venv/bin/activate ] && source venv/bin/activate

case "$1" in
	native)
		shift
		[ -f tests/native/build/libzyncore.so ] || tests/native/build_native.sh || exit 1
		export ZYNTEST_LOG=${ZYNTEST_LOG:-INFO}
		exec python3 -m pytest tests/native "$@"
		;;
	gui)
		shift
		exec xvfb-run -a python3 -m pytest "$@"
		;;
	*)
		exec python3 -m pytest "$@"
		;;
esac
