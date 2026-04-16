#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI configuration
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import os
import sys
import logging

# Zynthian specific modules
import zynconf


def get_env_int(env_var, default_val=0):
    try:
        return int(os.environ.get(env_var, str(default_val)))
    except:
        #logging.warning(f"Failed to retrieve environmental variable {env_var}")
        return default_val

# ------------------------------------------------------------------------------
# Log level and debuging
# ------------------------------------------------------------------------------


debug_thread = get_env_int('ZYNTHIAN_DEBUG_THREAD', 0)

log_level = get_env_int('ZYNTHIAN_LOG_LEVEL', logging.WARNING)
# log_level = logging.DEBUG

logging.basicConfig(format='%(levelname)s:%(module)s.%(funcName)s: %(message)s', stream=sys.stderr, level=log_level)
logging.getLogger().setLevel(level=log_level)

# Reduce log level for other modules
logging.getLogger("urllib3").setLevel(logging.WARNING)

logging.info("ZYNTHIAN-UI CONFIG ...")

if log_level == logging.DEBUG:
    import inspect
    def logging_call_stack():
        fnames = []
        stack = list(inspect.stack())
        stack.reverse()
        for i in range(len(stack) - 1):
            fnames.append(stack[i][3])
        logging.debug(f"Call Stack: {' -> '.join(fnames)}\n")
else:
    def logging_call_stack():
        pass

# ------------------------------------------------------------------------------
# Kit name and Wiring layout
# ------------------------------------------------------------------------------

kit_version = os.environ.get('ZYNTHIAN_KIT_VERSION', "CUSTOM")
logging.info(f"Kit Version: {kit_version}")
wiring_layout = os.environ.get('ZYNTHIAN_WIRING_LAYOUT', "TOUCH_ONLY")
if wiring_layout == "DUMMIES":
    wiring_layout = "TOUCH_ONLY"
    logging.info("No Wiring Layout configured. Only touch interface is available.")
else:
    logging.info(f"Wiring Layout: {wiring_layout}")
select_ctrl = 3


def check_kit_version(kits):
    for kit in kits:
        if kit_version.startswith(kit):
            return True
    return False


def check_wiring_layout(wls):
    for wl in wls:
        if wiring_layout.startswith(wl):
            return True
    return False

# ------------------------------------------------------------------------------
# GUI layout
# ------------------------------------------------------------------------------


gui_layout = os.environ.get('ZYNTHIAN_UI_GRAPHIC_LAYOUT', '')

if not gui_layout:
    if check_wiring_layout(["Z2", "V5", "TOUCH_ONLY"]):
        gui_layout = "Z2"
    else:
        gui_layout = "V4"

if gui_layout == "Z2":
    layout = {
        'name': 'Z2',
        'columns': 2,
        'rows': 4,
        'ctrl_pos': [
                (0, 1),
                (1, 1),
                (2, 1),
                (3, 1)
        ],
        'list_pos': (0, 0),
        'ctrl_orientation': 'horizontal',
        'ctrl_order': (0, 1, 2, 3),
        'ctrl_width': 0.25
    }
else:
    layout = {
        'name': 'V4',
        'columns': 3,
        'rows': 2,
        'ctrl_pos': [
                (0, 0),
                (1, 0),
                (0, 2),
                (1, 2)
        ],
        'list_pos': (0, 1),
        'ctrl_orientation': 'vertical',
        'ctrl_order': (0, 2, 1, 3),
        'ctrl_width': 0.23
    }

# ------------------------------------------------------------------------------
# Custom Switches Action Configuration
# ------------------------------------------------------------------------------

custom_switch_ui_actions = []
custom_switch_midi_events = []

zynswitch_bold_us = 1000 * 300
zynswitch_long_us = 1000 * 2000
zynswitch_bold_seconds = zynswitch_bold_us / 1000000
zynswitch_long_seconds = zynswitch_long_us / 1000000


def config_zynswitch_timing():
    global zynswitch_bold_us
    global zynswitch_long_us
    global zynswitch_bold_seconds
    global zynswitch_long_seconds
    try:
        zynswitch_bold_us = 1000 * get_env_int('ZYNTHIAN_UI_SWITCH_BOLD_MS', 300)
        zynswitch_long_us = 1000 * get_env_int('ZYNTHIAN_UI_SWITCH_LONG_MS', 2000)
        zynswitch_bold_seconds = zynswitch_bold_us / 1000000
        zynswitch_long_seconds = zynswitch_long_us / 1000000

    except Exception as err:
        logging.error("ERROR configuring zynswitch timing: {}".format(err))


def get_env_switch_action(varname):
    action = os.environ.get(varname, "").strip()
    if not action or action == "NONE":
        action = None
    return action


def config_custom_switches():
    global custom_switch_ui_actions
    global custom_switch_midi_events

    custom_switch_ui_actions = []
    custom_switch_midi_events = []

    for i in range(num_zynswitches - 4):
        cuias = None
        midi_event = None

        root_varname = "ZYNTHIAN_WIRING_CUSTOM_SWITCH_{:02d}".format(i+1)
        custom_type = os.environ.get(root_varname, "")

        if custom_type == "UI_ACTION_PUSH":
            cuias = {
                'P': get_env_switch_action(root_varname + "__UI_PUSH"),
                'S': "",
                'B': "",
                'L': "",
                'AP': get_env_switch_action(root_varname + "__UI_ALT_PUSH"),
                'AS': "",
                'AB': "",
                'AL': ""
            }
        elif custom_type == "UI_ACTION" or custom_type == "UI_ACTION_RELEASE":
            cuias = {
                'P': "",
                'S': get_env_switch_action(root_varname + "__UI_SHORT"),
                'B': get_env_switch_action(root_varname + "__UI_BOLD"),
                'L': get_env_switch_action(root_varname + "__UI_LONG"),
                'AP': "",
                'AS': get_env_switch_action(root_varname + "__UI_ALT_SHORT"),
                'AB': get_env_switch_action(root_varname + "__UI_ALT_BOLD"),
                'AL': get_env_switch_action(root_varname + "__UI_ALT_LONG")
            }
        elif custom_type != "":
            if custom_type == "MIDI_CC":
                evtype = 0xB
            elif custom_type == "MIDI_NOTE":
                evtype = 0x9
            elif custom_type == "MIDI_PROG_CHANGE":
                evtype = 0xC
            elif custom_type == "MIDI_CLOCK":
                evtype = 0xF8
            elif custom_type == "MIDI_TRANSPORT_START":
                evtype = 0xFA
            elif custom_type == "MIDI_TRANSPORT_CONTINUE":
                evtype = 0xFB
            elif custom_type == "MIDI_TRANSPORT_STOP":
                evtype = 0xFC
            elif custom_type == "CVGATE_IN":
                evtype = -4
            elif custom_type == "CVGATE_OUT":
                evtype = -5
            elif custom_type == "GATE_OUT":
                evtype = -6
            elif custom_type == "MIDI_CC_SWITCH":
                evtype = -7
            else:
                evtype = None

            if evtype:
                chan = os.environ.get(root_varname + "__MIDI_CHAN")
                try:
                    chan = int(chan) - 1
                    if chan < 0 or chan > 15:
                        chan = None
                except:
                    chan = None

                if evtype in (-4, -5):
                    num = os.environ.get(root_varname + "__CV_CHAN")
                else:
                    num = os.environ.get(root_varname + "__MIDI_NUM")

                try:
                    val = get_env_int(root_varname + "__MIDI_VAL")
                    val = max(min(127, val), 0)
                except:
                    val = 0

                try:
                    num = int(num)
                    if 0 <= num <= 127:
                        midi_event = {
                            'type': evtype,
                            'chan': chan,
                            'num': num,
                            'val': val
                        }
                except:
                    pass

        custom_switch_ui_actions.append(cuias)
        custom_switch_midi_events.append(midi_event)
    #logging.debug(f"CUSTOM_SWITCH_UI_ACTIONS => \n {custom_switch_ui_actions}")


def config_zynpot2switch():
    global zynpot2switch
    zynpot2switch = []

    if num_zynpots > 0:
        # Detect zynpot switches configuration (V5)
        for i, cuias in enumerate(custom_switch_ui_actions):
            # WARNING!! It assumes the zynpot switches are sorted!! => It should parse the indexes from CUIAs!
            try:
                if cuias['S'].startswith("V5_ZYNPOT_SWITCH"):
                    zynpot2switch.append(4 + i)
            except:
                pass

        # Default configuration for "classic layouts" => It discards V5 partial configurations!
        if len(zynpot2switch) < num_zynpots:
            zynpot2switch = [0, 1, 2, 3]

        logging.info(f"zynpot2switch => {zynpot2switch}")


# ------------------------------------------------------------------------------
# Zynaptik & Zyntof configuration
# ------------------------------------------------------------------------------

zynaptik_ad_midi_events = []
zynaptik_da_midi_events = []
zyntof_midi_events = []


def get_zynsensor_config(root_varname):
    midi_event = None

    event_type = os.environ.get(root_varname, "")
    if event_type == "MIDI_CC":
        evtype = 0xB
    elif event_type == "MIDI_PITCH_BEND":
        evtype = 0xE
    elif event_type == "MIDI_CHAN_PRESS":
        evtype = 0xD
    else:
        evtype = None

    if evtype:
        chan = os.environ.get(root_varname + "__MIDI_CHAN")
        try:
            chan = int(chan) - 1
            if chan < 0 or chan > 15:
                chan = None
        except:
            chan = None

        num = os.environ.get(root_varname + "__MIDI_NUM")
        try:
            num = int(num)
            if 0 <= num <= 127:
                midi_event = {
                    'type': evtype,
                    'chan': chan,
                    'num': num
                }
        except:
            pass

    return midi_event


def config_zynaptik():
    global zynaptik_ad_midi_events
    global zynaptik_da_midi_events

    zynaptik_ad_midi_events = []
    zynaptik_da_midi_events = []

    zynaptik_config = os.environ.get("ZYNTHIAN_WIRING_ZYNAPTIK_CONFIG")
    if zynaptik_config:
        # Zynaptik AD Action Configuration
        if "4xAD" in zynaptik_config:
            for i in range(4):
                root_varname = "ZYNTHIAN_WIRING_ZYNAPTIK_AD{:02d}".format(i+1)
                zynaptik_ad_midi_events.append(get_zynsensor_config(root_varname))

        # Zynaptik DA Action Configuration
        if "4xDA" in zynaptik_config:
            for i in range(4):
                root_varname = "ZYNTHIAN_WIRING_ZYNAPTIK_DA{:02d}".format(i+1)
                zynaptik_da_midi_events.append(get_zynsensor_config(root_varname))


def config_zyntof():
    global zyntof_midi_events
    zyntof_midi_events = []

    zyntof_config = os.environ.get("ZYNTHIAN_WIRING_ZYNTOF_CONFIG")
    if zyntof_config:
        # Zyntof Action Configuration
        n_zyntofs = int(zyntof_config)
        for i in range(0, n_zyntofs):
            root_varname = "ZYNTHIAN_WIRING_ZYNTOF{:02d}".format(i+1)
            zyntof_midi_events.append(get_zynsensor_config(root_varname))


# ------------------------------------------------------------------------------
# MIDI Configuration
# ------------------------------------------------------------------------------

# Setup MIDI options
def set_midi_config():
    global active_midi_channel, midi_prog_change_zs3, midi_bank_change, midi_fine_tuning
    global midi_usb_by_port, transport_clock_source, midi_filter_rules, midi_chanpress_cc
    global midi_network_enabled, midi_rtpmidi_enabled, midi_netump_enabled
    global midi_touchosc_enabled, bluetooth_enabled, ble_controller, midi_aubionotes_enabled

    # MIDI options
    midi_fine_tuning = float(os.environ.get('ZYNTHIAN_MIDI_FINE_TUNING', "440.0"))
    active_midi_channel = get_env_int('ZYNTHIAN_MIDI_ACTIVE_CHANNEL', 0)
    midi_prog_change_zs3 = get_env_int('ZYNTHIAN_MIDI_PROG_CHANGE_ZS3', 1)
    midi_bank_change = get_env_int('ZYNTHIAN_MIDI_BANK_CHANGE', 0)
    midi_usb_by_port = get_env_int("ZYNTHIAN_MIDI_USB_BY_PORT", 0)
    midi_network_enabled = get_env_int('ZYNTHIAN_MIDI_NETWORK_ENABLED', 0)
    midi_netump_enabled = get_env_int('ZYNTHIAN_MIDI_NETUMP_ENABLED', 0)
    midi_rtpmidi_enabled = get_env_int('ZYNTHIAN_MIDI_RTPMIDI_ENABLED', 0)
    midi_touchosc_enabled = get_env_int('ZYNTHIAN_MIDI_TOUCHOSC_ENABLED', 0)
    bluetooth_enabled = get_env_int('ZYNTHIAN_MIDI_BLE_ENABLED', 0)
    ble_controller = os.environ.get('ZYNTHIAN_MIDI_BLE_CONTROLLER', "")
    midi_aubionotes_enabled = get_env_int('ZYNTHIAN_MIDI_AUBIONOTES_ENABLED', 0)
    transport_clock_source = os.environ.get('ZYNTHIAN_MIDI_TRANSPORT_CLOCK_SOURCE', "Internal")

    # Filter Rules
    midi_filter_rules = os.environ.get('ZYNTHIAN_MIDI_FILTER_RULES', "")
    midi_filter_rules = midi_filter_rules.replace("\\n", "\n")
    midi_chanpress_cc = get_env_int('ZYNTHIAN_MIDI_CHANPRESS_CC', 0)


# Setup MIDI Master Channel options
def set_mmc_config():
    global master_midi_channel, master_midi_change_type, master_midi_note_cuia
    global master_midi_program_change_up, master_midi_program_change_down
    global master_midi_program_base, master_midi_bank_change_ccnum
    global master_midi_bank_change_up, master_midi_bank_change_down
    global master_midi_bank_change_down_ccnum, master_midi_bank_base

    # Master Channel Features
    master_midi_channel = int(os. environ.get("ZYNTHIAN_MIDI_MASTER_CHANNEL", 0))
    master_midi_channel -= 1
    if master_midi_channel > 15:
        master_midi_channel = 15
    if master_midi_channel >= 0:
        mmc_hex = hex(master_midi_channel)[2]
    else:
        mmc_hex = None

    # Predefined config for MMC Bank/Program change UP/DOWN (incremental)
    master_midi_change_type = os.environ.get("ZYNTHIAN_MIDI_MASTER_CHANGE_TYPE", "Roland")

    # Use LSB Bank by default
    master_midi_bank_change_ccnum = None
    if mmc_hex:
        try:
            master_midi_bank_change_ccnum = get_env_int("ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM", 0x20)
            # Use MSB Bank by default
            # master_midi_bank_change_ccnum = get_env_int("ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM", 0x00)
            logging.debug(f"MMC Bank Change CCNum: 0x{master_midi_bank_change_ccnum:02x}")
        except Exception as e:
            logging.error(f"Can't parse MMC Bank Change CCNum => {e}")

    mmpcu = os.environ.get('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_UP', "")
    master_midi_program_change_up = None
    if mmc_hex and len(mmpcu) == 4:
        try:
            ev = int("{:<06}".format(mmpcu.replace("#", mmc_hex)), 16)
            logging.debug(f"MMC Program Change UP: 0x{ev:02x}")
            master_midi_program_change_up = ev.to_bytes(3, 'big')
        except Exception as e:
            logging.error(f"Can't parse MMC Program Change UP => {e}")

    mmpcd = os.environ.get('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_DOWN', "")
    master_midi_program_change_down = None
    if mmc_hex and len(mmpcd) == 4:
        try:
            ev = int("{:<06}".format(mmpcd.replace("#", mmc_hex)), 16)
            logging.debug(f"MMC Program Change DOWN: 0x{ev:02x}")
            master_midi_program_change_down = ev.to_bytes(3, 'big')
        except Exception as e:
            logging.error(f"Can't parse MMC Program Change DOWN => {e}")

    mmbcu = os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_UP', "")
    master_midi_bank_change_up = None
    if mmc_hex and len(mmbcu) == 6:
        try:
            ev = int("{:<06}".format(mmbcu.replace("#", mmc_hex)), 16)
            logging.debug(f"MMC Bank Change UP: 0x{ev:02x}")
            master_midi_bank_change_up = ev.to_bytes(3, 'big')
        except Exception as e:
            logging.error(f"Can't parse MMC Bank Change UP => {e}")

    mmbcd = os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_DOWN', "")
    master_midi_bank_change_down = None
    try:
        if mmc_hex and len(mmbcd) == 6:
            ev = int("{:<06}".format(mmbcd.replace("#", mmc_hex)), 16)
            logging.debug(f"MMC Bank Change DOWN: 0x{ev:02x}")
            master_midi_bank_change_down = ev.to_bytes(3, 'big')
    except Exception as e:
        logging.error(f"Can't parse MMC Bank Change DOWN => {e}")

    # Master Note CUIA
    mmncuia_envar = os.environ.get('ZYNTHIAN_MIDI_MASTER_NOTE_CUIA', None)
    if mmncuia_envar is None:
        master_midi_note_cuia = zynconf.NoteCuiaDefault
    else:
        master_midi_note_cuia = {}
        for cuianote in mmncuia_envar.split('\\n'):
            cuianote = cuianote.strip()
            if cuianote:
                try:
                    parts = cuianote.split(':')
                    note = parts[0].strip()
                    cuia = parts[1].strip()
                    if note and cuia:
                        master_midi_note_cuia[note] = cuia
                    else:
                        raise Exception("Bad format!")
                except Exception as err:
                    logging.warning("Bad MIDI Master Note CUIA config {} => {}".format(cuianote, err))

# ------------------------------------------------------------------------------
# External storage (removable disks)
# ------------------------------------------------------------------------------


def get_external_storage_dirs(exdpath):
    return zynconf.get_external_storage_dirs(exdpath)

# ------------------------------------------------------------------------------
# UI Color Parameters
# ------------------------------------------------------------------------------


color_bg = os.environ.get('ZYNTHIAN_UI_COLOR_BG', "#000000")
color_tx = os.environ.get('ZYNTHIAN_UI_COLOR_TX', "#ffffff")
color_tx_off = os.environ.get('ZYNTHIAN_UI_COLOR_TX_OFF', "#e0e0e0")
color_on = os.environ.get('ZYNTHIAN_UI_COLOR_ON', "#ff0000")
color_off = os.environ.get('ZYNTHIAN_UI_COLOR_OFF', "#5a626d")
color_hl = os.environ.get('ZYNTHIAN_UI_COLOR_HL', "#00c000")
color_ml = os.environ.get('ZYNTHIAN_UI_COLOR_ML', "#f0f000")
color_low_on = os.environ.get('ZYNTHIAN_UI_COLOR_LOW_ON', "#b00000")
color_panel_bg = os.environ.get('ZYNTHIAN_UI_COLOR_PANEL_BG', "#3a424d")
color_panel_hl = os.environ.get('ZYNTHIAN_UI_COLOR_PANEL_HL', "#2a323d")
color_info = os.environ.get('ZYNTHIAN_UI_COLOR_INFO', "#8080ff")
color_midi = os.environ.get('ZYNTHIAN_UI_COLOR_MIDI', "#9090ff")
color_alt = os.environ.get('ZYNTHIAN_UI_COLOR_ALT', "#ff00ff")
color_alt2 = os.environ.get('ZYNTHIAN_UI_COLOR_ALT2', "#ff9000")
color_error = os.environ.get('ZYNTHIAN_UI_COLOR_ERROR', "#ff0000")
color_warn = os.environ.get('ZYNTHIAN_UI_COLOR_WARN', "#ff9000")

# Color Scheme
color_panel_bd = color_bg
color_panel_tx = color_tx
color_header_bg = color_bg
color_header_tx = color_tx
color_ctrl_bg_off = color_off
color_ctrl_bg_on = color_on
color_ctrl_tx = color_tx
color_ctrl_tx_off = color_tx_off
color_status_midi = color_midi
color_status_play = color_hl
color_status_record = color_low_on
color_status_play_midi = color_alt
color_status_play_seq = color_alt2
color_status_error = color_error
color_status_warn = color_warn

# ------------------------------------------------------------------------------
# Font Family
# ------------------------------------------------------------------------------

font_family = os.environ.get('ZYNTHIAN_UI_FONT_FAMILY', "Audiowide")
# font_family = "Helvetica" #=> the original ;-)
# font_family = "Economica" #=> small
# font_family = "Orbitron" #=> Nice, but too strange
# font_family = "Abel" #=> Quite interesting, also "Strait"

# ------------------------------------------------------------------------------
# Touch Options
# ------------------------------------------------------------------------------

touch_navigation = os.environ.get('ZYNTHIAN_UI_TOUCH_NAVIGATION', "")
force_enable_cursor = get_env_int('ZYNTHIAN_UI_ENABLE_CURSOR', 0)

if touch_navigation not in ("", "v5_keypad_left", "v5_keypad_right"):
    touch_navigation = "v5_keypad_left"
if wiring_layout == "TOUCH_ONLY" and not touch_navigation:
    touch_navigation = "v5_keypad_left"

# Configure switch actions for touch only configuration so it works with touch-keypad
if touch_navigation:
    logging.debug(f"TOUCH NAVIGATION = {touch_navigation}")
    if os.environ.get("ZYNTHIAN_WIRING_LAYOUT_CUSTOM_PROFILE", "") != "v5":
        config_dir = os.environ.get("ZYNTHIAN_CONFIG_DIR", "/zynthian/config")
        zynconf.load_plain_envars(f"{config_dir}/wiring-profiles/v5", True)
        os.environ["ZYNTHIAN_WIRING_SWITCHES"] = ",".join(36 * ["-1"])

# ------------------------------------------------------------------------------
# UI Options
# ------------------------------------------------------------------------------

restore_last_state = get_env_int('ZYNTHIAN_UI_RESTORE_LAST_STATE', 0)
snapshot_mixer_settings = get_env_int('ZYNTHIAN_UI_SNAPSHOT_MIXER_SETTINGS', 0)
show_cpu_status = get_env_int('ZYNTHIAN_UI_SHOW_CPU_STATUS', 0)
visible_mixer_strips = get_env_int('ZYNTHIAN_UI_VISIBLE_MIXER_STRIPS', 0)
visible_launchers = get_env_int('ZYNTHIAN_UI_VISIBLE_LAUNCHERS', 8)
ctrl_graph = get_env_int('ZYNTHIAN_UI_CTRL_GRAPH', 1)
control_test_enabled = get_env_int('ZYNTHIAN_UI_CONTROL_TEST_ENABLED', 0)
power_save_secs = 60 * get_env_int('ZYNTHIAN_UI_POWER_SAVE_MINUTES', 60)
preset_preload = get_env_int('ZYNTHIAN_UI_PRESET_PRELOAD', 1)

# ------------------------------------------------------------------------------
# Audio Options
# ------------------------------------------------------------------------------

rbpi_headphones = get_env_int('ZYNTHIAN_RBPI_HEADPHONES', 0)
enable_dpm = get_env_int('ZYNTHIAN_DPM', 1)
hotplug_audio_enabled = get_env_int('ZYNTHIAN_HOTPLUG_AUDIO', 0)
disabled_audio_in = os.environ.get('ZYNTHIAN_HOTPLUG_AUDIO_DISABLED_IN', "").split(',')
disabled_audio_out = os.environ.get('ZYNTHIAN_HOTPLUG_AUDIO_DISABLED_OUT', 'headphones,b1,b2').split(',')


# ------------------------------------------------------------------------------
# Text To Speech Options
# ------------------------------------------------------------------------------

tts_enabled = get_env_int('ZYNTHIAN_TTS_ENABLED', 1)
tts_engine = os.environ.get('ZYNTHIAN_TTS_ENGINE', "flite")
tts_gender = os.environ.get('ZYNTHIAN_TTS_GENDER', "m")
tts_speed = float(os.environ.get('ZYNTHIAN_TTS_SPEED', "1.0"))
tts_soundcard = os.environ.get('ZYNTHIAN_TTS_SOUNDCARD', "1")

# ------------------------------------------------------------------------------
# Networking Options
# ------------------------------------------------------------------------------

vncserver_enabled = get_env_int('ZYNTHIAN_VNCSERVER_ENABLED', 0)

# ------------------------------------------------------------------------------
# Player configuration
# ------------------------------------------------------------------------------

midi_play_loop = get_env_int('ZYNTHIAN_MIDI_PLAY_LOOP', 0)
audio_play_loop = get_env_int('ZYNTHIAN_AUDIO_PLAY_LOOP', 0)

# ------------------------------------------------------------------------------
# Experimental features
# ------------------------------------------------------------------------------

experimental_features = os.environ.get('ZYNTHIAN_EXPERIMENTAL_FEATURES', "").split(',')

# ------------------------------------------------------------------------------
# Sequence states
# ------------------------------------------------------------------------------

PAD_COLOUR_DISABLED = '#505050'
PAD_COLOUR_STATE_DISABLED = '#A0A0A0'
PAD_COLOUR_EMPTY = '#707070'
PAD_COLOUR_STARTING = '#FFBB00'
PAD_COLOUR_PLAYING = '#00FF00'
PAD_COLOUR_STOPPING = '#FF0000'
PAD_COLOUR_STOPPED = '#E0E0E0'
PAD_COLOUR_PHRASE = '#707070'
LAUNCHER_COLOUR = [
    # MIDI Channels 1..16 (offset 0..15)
    {"rgb": "#0000FF", "launchpad": 79,  "apc": 45},  #1:blue
    {"rgb": "#BBBB00", "launchpad": 13,  "apc": 13},  #2:yellow
    {"rgb": "#FF00FF", "launchpad": 53,  "apc": 53},  #3:magenta
    {"rgb": "#23C497", "launchpad": 33,  "apc": 33},  #4:lime green
    {"rgb": "#FF5400", "launchpad": 9,   "apc": 60},  #5:orange
    {"rgb": "#874CFF", "launchpad": 49,  "apc": 80},  #6:deep purple
    {"rgb": "#FF4C87", "launchpad": 57,  "apc": 57},  #7:hot pink
    {"rgb": "#2DB7CE", "launchpad": 37,  "apc": 37},  #8:cyan
    {"rgb": "#D2C7D4", "launchpad": 2,   "apc": 1},   #9:grey
    {"rgb": "#C9A869", "launchpad": 125, "apc": 127}, #10:light brown
    {"rgb": "#7BC783", "launchpad": 19,  "apc": 16},  #11:turquise
    {"rgb": "#EB8895", "launchpad": 4,   "apc": 4},   #12:pink
    {"rgb": "#CA92d4", "launchpad": 70,  "apc": 69},  #13:light purple
    {"rgb": "#4CFFB7", "launchpad": 24,  "apc": 20},  #14:green-blue
    {"rgb": "#3F94A2", "launchpad": 42,  "apc": 65},  #15:teal
    {"rgb": "#F5B169", "launchpad": 126, "apc": 10},  #16:light orange
    # Clip launchers 1..16 (offset 16..31)
    {"rgb": "#F5B169", "launchpad": 126, "apc": 10},  #17:light orange
    {"rgb": "#3F94A2", "launchpad": 42,  "apc": 65},  #18:teal
    {"rgb": "#4CFFB7", "launchpad": 24,  "apc": 20},  #19:green-blue
    {"rgb": "#CA92d4", "launchpad": 70,  "apc": 69},  #20:light purple
    {"rgb": "#EB8895", "launchpad": 4,   "apc": 4},   #21:pink
    {"rgb": "#7BC783", "launchpad": 19,  "apc": 16},  #22:turquise
    {"rgb": "#C9A869", "launchpad": 125, "apc": 127}, #23:light brown
    {"rgb": "#D2C7D4", "launchpad": 2,   "apc": 1},   #24:grey
    {"rgb": "#2DB7CE", "launchpad": 37,  "apc": 37},  #25:cyan
    {"rgb": "#FF4C87", "launchpad": 57,  "apc": 57},  #26:hot pink
    {"rgb": "#874CFF", "launchpad": 49,  "apc": 80},  #27:deep purple
    {"rgb": "#FF5400", "launchpad": 9,   "apc": 60},  #28:orange
    {"rgb": "#23C497", "launchpad": 33,  "apc": 33},  #29:lime green
    {"rgb": "#FF00FF", "launchpad": 53,  "apc": 53},  #30:magenta
    {"rgb": "#BBBB00", "launchpad": 13,  "apc": 13},  #31:yellow
    {"rgb": "#0000FF", "launchpad": 79,  "apc": 45},  #32:blue
    # Main / phrase launchers (offset 32)
    {"rgb": "#707070", "launchpad": 1,   "apc": 1}    #33:grey
]
#TODO: Choose clip launcher colours (currently just reversed 1-16)

LAUNCHER_PLAYING_COLOUR = {"rgb": "#009000", "launchpad": 21, "apc": 87} #green
LAUNCHER_STARTING_COLOUR = {"rgb": "#009000", "launchpad": 21, "apc": 87} #green
LAUNCHER_STOPPING_COLOUR = {"rgb": "#D00000", "launchpad": 5, "apc": 72} #red

def get_color_relux(hex_color):
    if len(hex_color) != 7:
        raise Exception("Passed %s into get_color_relux2(), needs to be in #RRGGBB format." % hex_color)
    R, G, B = [int(hex_color[x:x + 2], 16) for x in [1, 3, 5]]
    if R <= 10:
        Rg = R / 3294.0
    else:
        Rg = (R / 269.0 + 0.0513) ** 2.4
    if G <= 10:
        Gg = G / 3294.0
    else:
        Gg = (G / 269.0 + 0.0513) ** 2.4
    if B <= 10:
        Bg = B / 3294.0
    else:
        Bg = (B / 269.0 + 0.0513) ** 2.4
    return 0.2126 * Rg + 0.7152 * Gg + 0.0722 * Bg

def get_color_lux(hex_color):
    if len(hex_color) != 7:
        raise Exception("Passed %s into get_color_relux(), needs to be in #RRGGBB format." % hex_color)
    R, G, B = [int(hex_color[x:x + 2], 16) for x in [1, 3, 5]]
    # Counting the perceptive luminance - human eye favors green color...
    return (0.299 * R + 0.587 * G + 0.114 * B) / 255.0;

def get_contrast_ratio(hex_color1, hex_color2):
    L1 = get_color_relux(hex_color1)
    L2 = get_color_relux(hex_color2)
    if L1 > L2:
        return (L1 + 0.05) / (L2 + 0.05)
    else:
        return (L2 + 0.05) / (L1 + 0.05)

def color_variant(hex_color, brightness_offset=1):
    """ takes a color like #87c95f and produces a lighter or darker variant """
    if len(hex_color) != 7:
        raise Exception("Passed %s into color_variant(), needs to be in #RRGGBB format." % hex_color)
    rgb_int = [int(hex_color[x:x + 2], 16) for x in [1, 3, 5]]
    new_rgb_int = [val + brightness_offset for val in rgb_int]
    # make sure new values are between 0 and 255
    new_rgb_int = [min(255, max(0, i)) for i in new_rgb_int]
    # hex() produces "0x88", we want just "88"
    return "#" + "".join([hex(i)[2:].zfill(2) for i in new_rgb_int])

def color_scale(hex_color, brightness_scale=1.0):
    """ takes a color like #87c95f and produces a lighter or darker variant """
    if len(hex_color) != 7:
        raise Exception("Passed %s into color_scale(), needs to be in #87c95f format." % hex_color)
    rgb_int = [int(hex_color[x:x + 2], 16) for x in [1, 3, 5]]
    new_rgb_int = [int(val * brightness_scale) for val in rgb_int]
    # make sure new values are between 0 and 255
    new_rgb_int = [min(255, i) for i in new_rgb_int]
    # hex() produces "0x88", we want just "88"
    return "#" + "".join([hex(i)[2:].zfill(2) for i in new_rgb_int])

for i, value in enumerate(LAUNCHER_COLOUR):
    LAUNCHER_COLOUR[i]["rgb_light"] = color_variant(value["rgb"], 40)

# ------------------------------------------------------------------------------
# X11 Related Stuff
# ------------------------------------------------------------------------------

if "zynthian_main.py" in sys.argv[0]:
    import tkinter
    from PIL import Image, ImageTk

    def set_touch_keypad(enabled=True):
        global main_x, screen_width, screen_height, touch_shown
        if enabled:
            panel_width = display_width // 5
            if touch_navigation == "v5_keypad_left":
                main_x = panel_width
            screen_width = display_width - panel_width
            screen_height = 5 * display_height // 6
            touch_shown = 1
        else:
            main_x = 0
            screen_width = display_width
            screen_height = display_height
            touch_shown = 0
        # Resize and reposition root frame
        root_frame.configure(width=screen_width, height=screen_height)
        root_frame.place(x=main_x, y=main_y)
        root_frame.lift()

    def toggle_touch_keypad():
        set_touch_keypad(not touch_shown)

    #---------------------------------------------------------------------------
    # Root Frame Management
    #---------------------------------------------------------------------------

    ########################################
    #    LT    #       TOP      #    RT    #
    ########################################
    #          #                #          #
    #   LEFT   #      MAIN      #   RIGHT  #
    #          #                #          #
    ########################################
    #    LB    #     BOTTOM     #    RB    #
    #########################################

    try:
        # ------------------------------------------------------------------------------
        # Create & Configure Top Level window
        # ------------------------------------------------------------------------------

        top = tkinter.Tk()

        # Screen Size => Autodetect if None
        if os.environ.get('DISPLAY_WIDTH'):
            display_width = get_env_int('DISPLAY_WIDTH')
        else:
            try:
                display_width = top.winfo_screenwidth()
            except:
                logging.warning("Can't get screen width. Using default 320!")
                display_width = 320

        if os.environ.get('DISPLAY_HEIGHT'):
            display_height = get_env_int('DISPLAY_HEIGHT')
        else:
            try:
                display_height = top.winfo_screenheight()
            except:
                logging.warning("Can't get screen height. Using default 240!")
                display_height = 240

        # Adjust Root Window Geometry
        top.geometry(str(display_width)+'x'+str(display_height))
        top.maxsize(display_width, display_height)
        top.minsize(display_width, display_height)

        # Disable cursor for real Zynthian Boxes
        if force_enable_cursor or wiring_layout == "EMULATOR" or wiring_layout == "TOUCH_ONLY":
            top.config(cursor="arrow")
        else:
            top.config(cursor="none")

        # ------------------------------------------------------------------------------
        # Global Variables
        # ------------------------------------------------------------------------------

        # Root frame position
        main_x = 0
        main_y = 0

        # Screen dimensions within which to display main UI (excluding V5 buttons)
        screen_width = display_width
        screen_height = display_height

        # Global font size
        font_size = get_env_int('ZYNTHIAN_UI_FONT_SIZE', 16)
        if not font_size:
            font_size = int(display_width / 40)

        # Topbar variables
        if screen_width >= 800:
            topbar_height = screen_height // 12
            topbar_fs = int(1.5*font_size)
        else:
            topbar_height = screen_height // 10
            topbar_fs = int(1.1*font_size)

        # Global fonts
        font_listbox = (font_family, int(1.0*font_size))
        font_topbar = (font_family, topbar_fs)

        # ------------------------------------------------------------------------------
        # Setup Root Frame for the GUI
        # ------------------------------------------------------------------------------

        root_frame = tkinter.Frame(top,
                                  width=screen_width,
                                  height=screen_height,
                                  bg="#000000")

        # Configure columns
        root_frame.grid_propagate(False)
        root_frame.columnconfigure(1, weight=1)
        root_frame.rowconfigure(1, weight=1)
        root_frame.place(x=main_x, y=main_y)

        # Attach static methods to root frame
        # => Grid a GUI frame in the root grid MAIN area
        root_frame.grid_main = lambda frame: frame.grid(row=1, column=1, sticky='NEWS')
        # => Grid a GUI frame in the root grid RIGHT area
        root_frame.grid_right = lambda frame: frame.grid(row=1, column=2, sticky='NEWS')

        # ------------------------------------------------------------------------------
        # Setup touch keypad
        # ------------------------------------------------------------------------------

        if touch_navigation:
            # Create touch keypad frame and show it!
            try:
                from zyngui.zynthian_gui_touchkeypad_v5 import zynthian_gui_touchkeypad_v5
                touch_keypad = zynthian_gui_touchkeypad_v5()
                set_touch_keypad(get_env_int("ZYNTHIAN_TOUCH_SHOWN", 0))
            except Exception as e:
                logging.error(f"Can't start touch keypad => {e}")
                touch_shown = 0
                touch_keypad = None
        else:
            touch_shown = 0
            touch_keypad = None

        # ------------------------------------------------------------------------------
        # Loading Logo Animation
        # ------------------------------------------------------------------------------

        loading_imgs = []
        pil_frame = Image.open("./img/zynthian_gui_loading.gif")
        fw, fh = pil_frame.size
        fw2 = screen_width // 4 - 8
        fh2 = int(fh * fw2 / fw)
        nframes = 0
        while pil_frame:
            pil_frame2 = pil_frame.resize((fw2, fh2), Image.ANTIALIAS)
            # convert PIL image object to Tkinter PhotoImage object
            loading_imgs.append(ImageTk.PhotoImage(pil_frame2))
            nframes += 1
            try:
                pil_frame.seek(nframes)
            except EOFError:
                break
        # for i in range(13):
        # loading_imgs.append(tkinter.PhotoImage(file="./img/zynthian_gui_loading.gif", format="gif -index "+str(i)))

    except Exception as e:
        logging.error("ERROR initializing Tkinter graphic framework => {}".format(e))

    # ------------------------------------------------------------------------------
    # Initialize ZynCore low-level library
    # ------------------------------------------------------------------------------

    from zyncoder.zyncore import lib_zyncore_init

    # ------------------------------------------------------------------------------
    # Initialize and config control I/O subsystem: switches, analog I/O, ...
    # ------------------------------------------------------------------------------
    try:
        lib_zyncore = lib_zyncore_init()
    except Exception as e:
        logging.error(f"lib_zyncore: {e.args[0]} ({e.args[1]})")
        exit(200 + e.args[1])

    try:
        num_zynswitches = lib_zyncore.get_num_zynswitches()
        last_zynswitch_index = lib_zyncore.get_last_zynswitch_index()
        num_zynpots = lib_zyncore.get_num_zynpots()
    except Exception as e:
        logging.warning(f"Can't init control I/O subsytem: {e}")
        num_zynswitches = 0
        last_zynswitch_index = -1
        num_zynpots = 0
        #exit(200)

    config_zynswitch_timing()
    config_custom_switches()
    config_zynpot2switch()
    config_zynaptik()
    config_zyntof()

    # ------------------------------------------------------------------------------
    # Load MIDI config
    # ------------------------------------------------------------------------------

    try:
        set_midi_config()
        set_mmc_config()
    except Exception as e:
        logging.error("ERROR configuring MIDI: {}".format(e))

# ------------------------------------------------------------------------------
# Zynthian GUI object
# ------------------------------------------------------------------------------

zyngui = None

# ------------------------------------------------------------------------------
