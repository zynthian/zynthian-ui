#!/bin/bash
# Run zynslicer unit tests on a Zynthian/Linux host.
#
# The C API tests need a running JACK server. If JACK is not already running,
# this script starts a private dummy server and stops it again on exit. Stop
# zynthian-ui before running: the library uses the fixed JACK client name
# "zynslicer", so an already-running UI would make the test attach to its players.

set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PYTHON="${PYTHON:-python3}"
FORCE_BUILD=0

if [ "${1:-}" = "--build" ]; then
    FORCE_BUILD=1
    shift
fi

cd "$DIR" || exit 1

if [ "$FORCE_BUILD" = 1 ] || [ ! -f build/libzynslicer.so ]; then
    echo "Building zynslicer..."
    ./build.sh || exit 1
else
    echo "Using existing build/libzynslicer.so (pass --build to rebuild)"
fi

if ! command -v jack_lsp >/dev/null 2>&1; then
    echo "jack_lsp not found; install JACK tools or run on Zynthian" >&2
    exit 1
fi

JACKD_PID=""
cleanup() {
    if [ -n "$JACKD_PID" ]; then
        kill "$JACKD_PID" 2>/dev/null
        wait "$JACKD_PID" 2>/dev/null
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if ! jack_lsp >/dev/null 2>&1; then
    if ! command -v jackd >/dev/null 2>&1; then
        echo "No JACK server running and jackd not found" >&2
        exit 1
    fi
    echo "Starting temporary dummy JACK server..."
    jackd -d dummy -r 48000 -p 1024 >build/jackd-test.log 2>&1 &
    JACKD_PID=$!
    for _ in $(seq 1 50); do
        if jack_lsp >/dev/null 2>&1; then
            break
        fi
        sleep 0.1
    done
    if ! jack_lsp >/dev/null 2>&1; then
        echo "Failed to start dummy JACK server; see build/jackd-test.log" >&2
        exit 1
    fi
fi

if jack_lsp 2>/dev/null | grep -q '^zynslicer:'; then
    echo "A JACK client named 'zynslicer' is already running." >&2
    echo "Stop zynthian-ui (or the old test run) before running these tests." >&2
    exit 1
fi

api_rc=0
slicing_rc=0

echo
echo "=== C API tests ==="
"$PYTHON" unit_tests.py
api_rc=$?

echo
echo "=== Slicer engine tests ==="
"$PYTHON" "$DIR/../../zyngine/zynthian_engine_slicer_test.py"
slicing_rc=$?

if [ "$api_rc" -ne 0 ] || [ "$slicing_rc" -ne 0 ]; then
    echo
    echo "Tests failed (C API: $api_rc, slicer engine: $slicing_rc)" >&2
    exit 1
fi

echo
echo "All tests passed"
