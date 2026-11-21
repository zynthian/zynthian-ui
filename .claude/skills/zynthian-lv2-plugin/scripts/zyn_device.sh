#!/bin/bash
# Build, install and check LV2 plugins / zynthian widgets on a zynthian.
# Host: $ZYNTHIAN_HOST (default zynthian.lan), user root, ssh key auth.
#
#   zyn_device.sh plugins [filter]        installed LV2 plugins (JSON)
#   zyn_device.sh ports <URI>             ports & UIs of a plugin (JSON)
#   zyn_device.sh check <URI>             ports summary, UIs and zynthian widget resolution
#   zyn_device.sh build <project_dir>     rsync project + make on the device
#   zyn_device.sh install <project_dir>   copy bin/<symbol>.lv2 to zynthian-plugins/lv2, touch lv2.stamp; first time
#                                         only: regenerate_engines_db.sh + enable it in the engines DB
#   zyn_device.sh widget <bundle_dir>     install a widget extension bundle into lv2-widgets, touch lv2.stamp
#   zyn_device.sh shot [:0|:1]            screenshot (zynthian display :0, VNC display :1) -> local PNG path
#   zyn_device.sh log [minutes]           errors and widget/jalv messages of the UI service

set -e
HOST="${ZYNTHIAN_HOST:-zynthian.lan}"
SSH="ssh -o ConnectTimeout=10 -o LogLevel=ERROR root@$HOST"
HERE="$(cd "$(dirname "$0")" && pwd)"
ENV="source /zynthian/config/zynthian_envars.sh >/dev/null 2>&1"
REMOTE_SRC="${ZYN_REMOTE_SRC:-/zynthian/zynthian-sw/plugins}"
TMPDIR_LOCAL="${CLAUDE_JOB_DIR:+$CLAUDE_JOB_DIR/tmp}"
TMPDIR_LOCAL="${TMPDIR_LOCAL:-/tmp}"

die() { echo "ERROR: $*" >&2; exit 1; }

lv2py() {  # run lv2_ports.py on the device
	$SSH "bash -c '$ENV; cd /tmp; python3 - $(printf '%q ' "$@")'" < "$HERE/lv2_ports.py"
}

project_symbol() {  # symbol of a DPF project = spec.json "symbol"
	python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["symbol"])' "$1/spec.json"
}

project_uri() {  # plugin URI of a DPF project = DISTRHO_PLUGIN_URI (the code is the truth, not spec.json)
	sed -n 's/^#define DISTRHO_PLUGIN_URI *"\(.*\)"/\1/p' "$1"/plugins/*/DistrhoPluginInfo.h | head -1
}

cmd="$1"; shift || true
case "$cmd" in
plugins)
	lv2py plugins "${1:-}"
	;;
ports)
	[ -n "$1" ] || die "usage: ports <URI>"
	lv2py ports "$1"
	;;
check)
	[ -n "$1" ] || die "usage: check <URI>"
	lv2py summary "$1"
	echo "zynthian widget:"
	lv2py widget "$1" 2>/dev/null | sed 's/^/  /'
	;;
build)
	[ -d "$1" ] || die "usage: build <project_dir>"
	dir="$(cd "$1" && pwd)"; sym="$(project_symbol "$dir")"
	[ -d "$dir/dpf/dgl" ] || die "DPF submodule missing: git -C $dir submodule update --init --recursive"
	echo "== rsync $dir -> $HOST:$REMOTE_SRC/$sym"
	$SSH "mkdir -p $REMOTE_SRC/$sym"
	rsync -a --delete --exclude '/bin/' --exclude 'build/' --exclude '.git/' --exclude '__pycache__/' \
		-e "ssh -o LogLevel=ERROR" "$dir/" "root@$HOST:$REMOTE_SRC/$sym/"
	echo "== make on $HOST"
	$SSH "cd $REMOTE_SRC/$sym && make -j4 2>&1 | grep -v '^Compiling\|^Creating\|^Linking' ; exit \${PIPESTATUS[0]}"
	$SSH "ls -la $REMOTE_SRC/$sym/bin/$sym.lv2"
	;;
install)
	[ -d "$1" ] || die "usage: install <project_dir>"
	dir="$(cd "$1" && pwd)"; sym="$(project_symbol "$dir")"; uri="$(project_uri "$dir")"
	$SSH "test -f $REMOTE_SRC/$sym/bin/$sym.lv2/manifest.ttl" || die "not built on $HOST: run build first"
	echo "== copy $sym.lv2 -> /zynthian/zynthian-plugins/lv2"
	$SSH "rsync -a --delete $REMOTE_SRC/$sym/bin/$sym.lv2/ /zynthian/zynthian-plugins/lv2/$sym.lv2/"
	if $SSH "bash -c '$ENV; cd /tmp; python3 - indb \"$uri\"'" < "$HERE/device_install.py"; then
		# Update: the plugin is already in the engines DB, no need to regenerate it
		$SSH "bash -c '$ENV; touch \$ZYNTHIAN_CONFIG_DIR/lv2.stamp'"
		echo "Updated $sym.lv2 (already in the engines DB; lv2.stamp touched)."
	else
		# First install: add it to the engines DB (disabled by default), then enable it
		echo "== regenerate_engines_db.sh (first install)"
		$SSH "bash -c '$ENV; \$ZYNTHIAN_SYS_DIR/sbin/regenerate_engines_db.sh 2>&1 | grep -v \"^DEBUG\|^INFO\" | tail -5'"
		echo "== enable in the engines DB"
		$SSH "bash -c '$ENV; cd /tmp; python3 - enable \"$uri\"'" < "$HERE/device_install.py"
		$SSH "bash -c '$ENV; touch \$ZYNTHIAN_CONFIG_DIR/lv2.stamp'"
		echo "Installed $sym.lv2 (added to the engines DB and enabled; lv2.stamp touched)."
	fi
	echo "Running instances keep the old code: use 'Reload' in the processor options."
	;;
widget)
	[ -d "$1" ] || die "usage: widget <bundle_dir>"
	b="$(cd "$1" && pwd)"; name="$(basename "$b")"
	case "$name" in *.lv2) ;; *) die "not an LV2 bundle dir: $name" ;; esac
	rsync -a --delete --exclude '__pycache__/' -e "ssh -o LogLevel=ERROR" "$b/" \
		"root@$HOST:/zynthian/zynthian-plugins/lv2-widgets/$name/"
	$SSH "bash -c '$ENV; touch \$ZYNTHIAN_CONFIG_DIR/lv2.stamp'"
	echo "Installed /zynthian/zynthian-plugins/lv2-widgets/$name (lv2.stamp touched): show the widget again to load it."
	;;
shot)
	disp="${1:-:0}"; out="$TMPDIR_LOCAL/zynshot_$(date +%H%M%S).png"
	$SSH "DISPLAY=$disp import -window root /tmp/zynshot.png" || die "screenshot failed (is display $disp running?)"
	scp -q -o LogLevel=ERROR "root@$HOST:/tmp/zynshot.png" "$out"
	echo "$out"
	;;
log)
	mins="${1:-5}"
	$SSH "for u in zynthian zynthian_debug; do systemctl -q is-active \$u && journalctl -u \$u --since -${mins}min --no-pager; done" \
		| grep -iE "error|traceback|exception|widget|jalv|lv2 data" | grep -v "KeyError: 'drawbar'" | tail -60
	;;
*)
	sed -n '2,15p' "$0"
	exit 1
	;;
esac
