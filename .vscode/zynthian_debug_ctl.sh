#!/bin/bash
# Control remote debugging of the zynthian UI service from the dev machine.
# Usage: zynthian_debug_ctl.sh auto|on|wait|off|tunnel
#   auto   - attach to running debugpy if listening, else restart as 'on'
#   on     - restart zynthian with debugpy listening (UI starts normally)
#   wait   - restart zynthian with debugpy listening, startup blocks until attach
#   off    - remove debug config and restart zynthian normally
#   tunnel - make sure an ssh tunnel localhost:$PORT -> device:$PORT exists
HOST=${ZYNTHIAN_HOST:-zynthian-v5}
PORT=${ZYNTHIAN_DEBUGPY_PORT:-5678}
DROPIN=/etc/systemd/system/zynthian.service.d/debugpy.conf

tunnel() {
	nc -z 127.0.0.1 "$PORT" 2>/dev/null && return 0
	ssh -fN -o ExitOnForwardFailure=yes -L "$PORT:127.0.0.1:$PORT" "$HOST"
}

wait_port() {
	# Wait for debugpy to listen on the device (UI takes a few seconds to start)
	ssh "$HOST" "for i in \$(seq 60); do ss -ltn | grep -q ':$PORT ' && exit 0; sleep 0.5; done; echo 'debugpy not listening' >&2; exit 1"
}

enable() {
	ssh "$HOST" "mkdir -p ${DROPIN%/*} && printf '[Service]\nEnvironment=ZYNTHIAN_DEBUGPY=127.0.0.1:$PORT\nEnvironment=ZYNTHIAN_DEBUGPY_WAIT=$1\nEnvironment=ZYNTHIAN_LOG_LEVEL=10\n' > $DROPIN && systemctl daemon-reload && systemctl restart zynthian" || exit 1
	wait_port && tunnel
}

is_listening() {
	ssh "$HOST" "ss -ltn | grep -q ':$PORT '"
}

case "$1" in
	auto) if is_listening; then echo "debugpy already listening on $HOST:$PORT - attaching"; tunnel; else enable 0; fi ;;
	on) enable 0 ;;
	wait) enable 1 ;;
	off) ssh "$HOST" "rm -f $DROPIN && systemctl daemon-reload && systemctl restart zynthian" ;;
	tunnel) tunnel ;;
	*) echo "Usage: $0 auto|on|wait|off|tunnel" >&2; exit 2 ;;
esac
