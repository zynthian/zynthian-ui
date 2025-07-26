#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI configuration
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# ------------------------------------------------------------------------------
# Log level and debuging
# ------------------------------------------------------------------------------

debug_thread = int(os.environ.get('ZYNTHIAN_DEBUG_THREAD', "0"))

log_level = int(os.environ.get('ZYNTHIAN_LOG_LEVEL', logging.WARNING))
# log_level = logging.DEBUG

logging.basicConfig(format='%(levelname)s:%(module)s.%(funcName)s: %(message)s', stream=sys.stderr, level=log_level)
logging.getLogger().setLevel(level=log_level)

# Reduce log level for other modules
logging.getLogger("urllib3").setLevel(logging.WARNING)

logging.info("ZYNTHIAN-UI CONFIG ...")

# ------------------------------------------------------------------------------
# Wiring layout
# ------------------------------------------------------------------------------

wiring_layout = os.environ.get('ZYNTHIAN_WIRING_LAYOUT', "TOUCH_ONLY")
if wiring_layout in ("TOUCH_ONLY", "DUMMIES"):
    wiring_layout = "TOUCH_ONLY"
    logging.info("No Wiring Layout configured. Only touch interface is available.")
else:
    logging.info("Wiring Layout %s" % wiring_layout)

select_ctrl = 3


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
    if check_wiring_layout(["Z2", "V5"]):
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
        zynswitch_bold_us = 1000 * int(os.environ.get('ZYNTHIAN_UI_SWITCH_BOLD_MS', 300))
        zynswitch_long_us = 1000 * int(os.environ.get('ZYNTHIAN_UI_SWITCH_LONG_MS', 2000))
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
                    val = int(os.environ.get(root_varname + "__MIDI_VAL"))
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


def set_midi_config():
    global active_midi_channel, preset_preload_noteon, midi_prog_change_zs3
    global midi_bank_change, midi_fine_tuning
    global midi_filter_rules, midi_sys_enabled, midi_usb_by_port
    global midi_network_enabled, midi_rtpmidi_enabled, midi_netump_enabled
    global midi_touchosc_enabled, bluetooth_enabled, ble_controller, midi_aubionotes_enabled
    global transport_clock_source
    global master_midi_channel, master_midi_change_type, master_midi_note_cuia
    global master_midi_program_change_up, master_midi_program_change_down
    global master_midi_program_base, master_midi_bank_change_ccnum
    global master_midi_bank_change_up, master_midi_bank_change_down
    global master_midi_bank_change_down_ccnum, master_midi_bank_base

    # MIDI options
    midi_fine_tuning = float(os.environ.get('ZYNTHIAN_MIDI_FINE_TUNING', "440.0"))
    active_midi_channel = int(os.environ.get('ZYNTHIAN_MIDI_ACTIVE_CHANNEL', "0"))
    midi_prog_change_zs3 = int(os.environ.get('ZYNTHIAN_MIDI_PROG_CHANGE_ZS3', "1"))
    midi_bank_change = int(os.environ.get('ZYNTHIAN_MIDI_BANK_CHANGE', "0"))
    preset_preload_noteon = int(os.environ.get('ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON', "1"))
    midi_sys_enabled = int(os.environ.get('ZYNTHIAN_MIDI_SYS_ENABLED', "1"))
    midi_usb_by_port = int(os.environ.get("ZYNTHIAN_MIDI_USB_BY_PORT", "0"))
    midi_network_enabled = int(os.environ.get('ZYNTHIAN_MIDI_NETWORK_ENABLED', "0"))
    midi_netump_enabled = int(os.environ.get('ZYNTHIAN_MIDI_NETUMP_ENABLED', "0"))
    midi_rtpmidi_enabled = int(os.environ.get('ZYNTHIAN_MIDI_RTPMIDI_ENABLED', "0"))
    midi_touchosc_enabled = int(os.environ.get('ZYNTHIAN_MIDI_TOUCHOSC_ENABLED', "0"))
    bluetooth_enabled = int(os.environ.get('ZYNTHIAN_MIDI_BLE_ENABLED', "0"))
    ble_controller = os.environ.get('ZYNTHIAN_MIDI_BLE_CONTROLLER', "")
    midi_aubionotes_enabled = int(os.environ.get('ZYNTHIAN_MIDI_AUBIONOTES_ENABLED', "0"))
    transport_clock_source = int(os.environ.get('ZYNTHIAN_MIDI_TRANSPORT_CLOCK_SOURCE', "0"))

    # Filter Rules
    midi_filter_rules = os.environ.get('ZYNTHIAN_MIDI_FILTER_RULES', "")
    midi_filter_rules = midi_filter_rules.replace("\\n", "\n")

    # Master Channel Features
    master_midi_channel = int(os. environ.get("ZYNTHIAN_MIDI_MASTER_CHANNEL", 0))
    master_midi_channel -= 1
    if master_midi_channel > 15:
        master_midi_channel = 15
    if master_midi_channel >= 0:
        mmc_hex = hex(master_midi_channel)[2]
    else:
        mmc_hex = None

    master_midi_change_type = os.environ.get("ZYNTHIAN_MIDI_MASTER_CHANGE_TYPE", "Roland")

    # Use LSB Bank by default
    master_midi_bank_change_ccnum = int(os.environ.get("ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM", 0x20))
    # Use MSB Bank by default
    # master_midi_bank_change_ccnum = int(os.environ.get("ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM", 0x00))

    mmpcu = os.environ.get('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_UP', "")
    if mmc_hex and len(mmpcu) == 4:
        master_midi_program_change_up = int("{:<06}".format(mmpcu.replace("#", mmc_hex)), 16)
    else:
        master_midi_program_change_up = None

    mmpcd = os.environ.get('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_DOWN', "")
    if mmc_hex and len(mmpcd) == 4:
        master_midi_program_change_down = int("{:<06}".format(mmpcd.replace("#", mmc_hex)), 16)
    else:
        master_midi_program_change_down = None

    mmbcu = os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_UP', "")
    if mmc_hex and len(mmbcu) == 6:
        master_midi_bank_change_up = int("{:<06}".format(mmbcu.replace("#", mmc_hex)), 16)
    else:
        master_midi_bank_change_up = None

    mmbcd = os.environ.get('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_DOWN', "")
    if mmc_hex and len(mmbcd) == 6:
        master_midi_bank_change_down = int("{:<06}".format(mmbcd.replace("#", mmc_hex)), 16)
    else:
        master_midi_bank_change_down = None

    logging.debug("MMC Bank Change CCNum: {}".format(master_midi_bank_change_ccnum))
    logging.debug("MMC Bank Change UP: {}".format(master_midi_bank_change_up))
    logging.debug("MMC Bank Change DOWN: {}".format(master_midi_bank_change_down))
    logging.debug("MMC Program Change UP: {}".format(master_midi_program_change_up))
    logging.debug("MMC Program Change DOWN: {}".format(master_midi_program_change_down))

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
color_hl = os.environ.get('ZYNTHIAN_UI_COLOR_HL', "#00b000")
color_ml = os.environ.get('ZYNTHIAN_UI_COLOR_ML', "#f0f000")
color_low_on = os.environ.get('ZYNTHIAN_UI_COLOR_LOW_ON', "#b00000")
color_panel_bg = os.environ.get('ZYNTHIAN_UI_COLOR_PANEL_BG', "#3a424d")
color_panel_hl = os.environ.get('ZYNTHIAN_UI_COLOR_PANEL_HL', "#2a323d")
color_info = os.environ.get('ZYNTHIAN_UI_COLOR_INFO', "#8080ff")
color_midi = os.environ.get('ZYNTHIAN_UI_COLOR_MIDI', "#9090ff")
color_alt = os.environ.get('ZYNTHIAN_UI_COLOR_ALT', "#ff00ff")
color_alt2 = os.environ.get('ZYNTHIAN_UI_COLOR_ALT2', "#ff9000")
color_error = os.environ.get('ZYNTHIAN_UI_COLOR_ERROR', "#ff0000")

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

touch_navigation = os.environ.get('ZYNTHIAN_UI_TOUCH_NAVIGATION2', '_UNDEF_')

# Backward compatibility
if touch_navigation == "_UNDEF_":
    touch_navigation = os.environ.get('ZYNTHIAN_UI_TOUCH_NAVIGATION', '')
    if touch_navigation == "1":
        touch_navigation = "touch_widgets"
    elif touch_navigation == "0":
        touch_keypad = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD', '')
        if touch_keypad == "V5":
            touch_navigation = "v5_keypad_left"

match touch_navigation:
    case "touch_widgets":
        enable_touch_navigation = True
        touch_keypad_option = ""
        touch_keypad_side_left = True
        enable_touch_controller_switches = 1
        main_screen_column = 0
    case "v5_keypad_left":
        enable_touch_navigation = False
        touch_keypad_option = "V5"
        touch_keypad_side_left = True
        enable_touch_controller_switches = 1
        main_screen_column = 1
    case "v5_keypad_right":
        enable_touch_navigation = False
        touch_keypad_option = "V5"
        touch_keypad_side_left = False
        enable_touch_controller_switches = 1
        main_screen_column = 0
    case _:
        enable_touch_navigation = False
        touch_keypad_option = ""
        touch_keypad_side_left = True
        enable_touch_controller_switches = 0
        main_screen_column = 0

try:
    force_enable_cursor = int(os.environ.get('ZYNTHIAN_UI_ENABLE_CURSOR', 0))
except:
    force_enable_cursor = 0

# Configure switch actions for touch only configuration so it works with touch-keypad
if touch_keypad_option == "V5" and wiring_layout =="TOUCH_ONLY":
    if os.environ.get("ZYNTHIAN_WIRING_LAYOUT_CUSTOM_PROFILE", "") != "v5":
        config_dir = os.environ.get("ZYNTHIAN_CONFIG_DIR", "/zynthian/config")
        zynconf.load_plain_envars(f"{config_dir}/wiring-profiles/v5", True)
        os.environ["ZYNTHIAN_WIRING_SWITCHES"] = ",".join(36 * ["-1"])

# ------------------------------------------------------------------------------
# UI Options
# ------------------------------------------------------------------------------

restore_last_state = int(os.environ.get('ZYNTHIAN_UI_RESTORE_LAST_STATE', 0))
snapshot_mixer_settings = int(os.environ.get('ZYNTHIAN_UI_SNAPSHOT_MIXER_SETTINGS', 0))
show_cpu_status = int(os.environ.get('ZYNTHIAN_UI_SHOW_CPU_STATUS', 0))
visible_mixer_strips = int(os.environ.get('ZYNTHIAN_UI_VISIBLE_MIXER_STRIPS', 0))
ctrl_graph = int(os.environ.get('ZYNTHIAN_UI_CTRL_GRAPH', 1))
control_test_enabled = int(os.environ.get('ZYNTHIAN_UI_CONTROL_TEST_ENABLED', 0))
power_save_secs = 60 * int(os.environ.get('ZYNTHIAN_UI_POWER_SAVE_MINUTES', 60))

# ------------------------------------------------------------------------------
# Audio Options
# ------------------------------------------------------------------------------

rbpi_headphones = int(os.environ.get('ZYNTHIAN_RBPI_HEADPHONES', 0))
enable_dpm = int(os.environ.get('ZYNTHIAN_DPM', True))
hotplug_audio_enabled = os.environ.get('ZYNTHIAN_HOTPLUG_AUDIO', False) == "True"
disabled_audio_in = os.environ.get('ZYNTHIAN_HOTPLUG_AUDIO_DISABLED_IN', "").split(',')
disabled_audio_out = os.environ.get('ZYNTHIAN_HOTPLUG_AUDIO_DISABLED_OUT', 'headphones,b1,b2').split(',')

# ------------------------------------------------------------------------------
# Networking Options
# ------------------------------------------------------------------------------

vncserver_enabled = int(os.environ.get('ZYNTHIAN_VNCSERVER_ENABLED', 0))

# ------------------------------------------------------------------------------
# Player configuration
# ------------------------------------------------------------------------------

midi_play_loop = int(os.environ.get('ZYNTHIAN_MIDI_PLAY_LOOP', 0))
audio_play_loop = int(os.environ.get('ZYNTHIAN_AUDIO_PLAY_LOOP', 0))

# ------------------------------------------------------------------------------
# Experimental features
# ------------------------------------------------------------------------------

experimental_features = os.environ.get('ZYNTHIAN_EXPERIMENTAL_FEATURES', "").split(',')

# ------------------------------------------------------------------------------
# Sequence states
# ------------------------------------------------------------------------------

PAD_COLOUR_DISABLED = '#303030'
PAD_COLOUR_DISABLED_LIGHT = '#505050'
PAD_COLOUR_STARTING = '#ffbb00'
PAD_COLOUR_PLAYING = '#00d000'
PAD_COLOUR_STOPPING = 'red'
PAD_COLOUR_GROUP = [
    '#662426',			# Red Granate
    '#3c6964',			# Blue Aguamarine
    '#4d6817',			# Green Pistacho
    '#664980',			# Lila
    '#4C709A',			# Mid Blue
    '#4C94CC',			# Sky Blue
    '#006000',			# Dark Green
    '#B7AA5E',  		# Ocre
    '#996633',  		# Maroon
    '#746360',			# Dark Grey
    '#D07272',			# Pink
    '#000060',			# Blue sat.
    '#048C8C',			# Turquesa
    '#f46815',			# Orange
    '#BF9C7C',			# Light Maroon
    '#56A556',			# Light Green
    '#FC6CB4',			# 7 medium
    '#CC8464',			# 8 medium
    '#4C94CC',			# 9 medium
    '#B454CC',			# 10 medium
    '#B08080',			# 11 medium
    '#0404FC', 			# 12 light
    '#9EBDAC',			# 13 light
    '#FF13FC',			# 14 light
    '#3080C0',			# 15 light
    '#9C7CEC'			# 16 light
]


def color_variant(hex_color, brightness_offset=1):
    """ takes a color like #87c95f and produces a lighter or darker variant """
    if len(hex_color) != 7:
        raise Exception("Passed %s into color_variant(), needs to be in #87c95f format." % hex_color)
    rgb_hex = [hex_color[x:x + 2] for x in [1, 3, 5]]
    new_rgb_int = [int(hex_value, 16) + brightness_offset for hex_value in rgb_hex]
    # make sure new values are between 0 and 255
    new_rgb_int = [min([255, max([0, i])]) for i in new_rgb_int]
    # hex() produces "0x88", we want just "88"
    return "#" + "".join([hex(i)[2:].zfill(2) for i in new_rgb_int])


PAD_COLOUR_GROUP_LIGHT = [color_variant(c, 40) for c in PAD_COLOUR_GROUP]

# ------------------------------------------------------------------------------
# X11 Related Stuff
# ------------------------------------------------------------------------------

if "zynthian_main.py" in sys.argv[0]:
    import tkinter
    from PIL import Image, ImageTk

    try:
        # ------------------------------------------------------------------------------
        # Create & Configure Top Level window
        # ------------------------------------------------------------------------------

        top = tkinter.Tk()

        # Screen Size => Autodetect if None
        if os.environ.get('DISPLAY_WIDTH'):
            display_width = int(os.environ.get('DISPLAY_WIDTH'))
        else:
            try:
                display_width = top.winfo_screenwidth()
            except:
                logging.warning("Can't get screen width. Using default 320!")
                display_width = 320

        if os.environ.get('DISPLAY_HEIGHT'):
            display_height = int(os.environ.get('DISPLAY_HEIGHT'))
        else:
            try:
                display_height = top.winfo_screenheight()
            except:
                logging.warning("Can't get screen height. Using default 240!")
                display_height = 240

        # Global font size
        font_size = int(os.environ.get('ZYNTHIAN_UI_FONT_SIZE', None))
        if not font_size:
            font_size = int(display_width / 40)

        touch_keypad = None
        # Touch Keypad enabled =>
        if touch_keypad_option == 'V5':
            # Screen dimensions < Display dimensions
            touch_keypad_side_width = display_height // 3
            touch_keypad_bottom_height = display_height // 6
            screen_width = display_width - touch_keypad_side_width
            screen_height = display_height - touch_keypad_bottom_height
            # Create touch keypad frame and show it!
            try:
                from zyngui.zynthian_gui_touchkeypad_v5 import zynthian_gui_touchkeypad_v5
                touch_keypad = zynthian_gui_touchkeypad_v5(top, side_width=touch_keypad_side_width, left_side=touch_keypad_side_left)
                touch_keypad.show()
            except Exception as e:
                logging.error(f"Can't start touch keypad {touch_keypad_option} => {e}")

        # Touch Keypad disabled or failed to start =>
        if not touch_keypad:
            # Screen dimensions = Display dimensions
            touch_keypad_side_width = 0
            touch_keypad_bottom_height = 0
            screen_width = display_width
            screen_height = display_height

        # Geometric params
        button_width = screen_width // 4
        if screen_width >= 800:
            topbar_height = screen_height // 12
            topbar_fs = int(1.5*font_size)
        else:
            topbar_height = screen_height // 10
            topbar_fs = int(1.1*font_size)

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

        # Fonts
        font_listbox = (font_family, int(1.0*font_size))
        font_topbar = (font_family, topbar_fs)
        font_buttonbar = (font_family, int(0.8*font_size))

        # Loading Logo Animation
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
        config_zynswitch_timing()
        config_custom_switches()
        config_zynpot2switch()
        config_zynaptik()
        config_zyntof()
    except Exception as e:
        logging.error(f"Can't init control I/O subsytem: {e}")
        exit(200)

    # ------------------------------------------------------------------------------
    # Load MIDI config
    # ------------------------------------------------------------------------------

    try:
        set_midi_config()
    except Exception as e:
        logging.error("ERROR configuring MIDI: {}".format(e))

# ------------------------------------------------------------------------------
# Zynthian GUI object
# ------------------------------------------------------------------------------

zyngui = None

# ------------------------------------------------------------------------------
