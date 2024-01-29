# -----------------------------------------------------------------------------
# Use it like this:
# Run once:
# > source zynthian_debug.sh
# Run many:
# > ./zynthian_main.py
# -----------------------------------------------------------------------------

#killall -9 startx
#killall -9 xinit
#rm -f /tmp/.X0-lock
startx xterm -- :0 &
export DISPLAY=:0
export ZYNTHIAN_LOG_LEVEL=10
export ZYNTHIAN_DEBUG_THREAD=1
export ZYNTHIAN_UI_POWER_SAVE_MINUTES="0"
powersave_control.sh off
#./zynthian_main.py
