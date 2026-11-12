# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian State Model Schema
#
# Copyright (C) 2022-2026 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
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

ZynthianState = {
    "schema_version": 6,  # Version of state (snapshot) model
    "last_snapshot_fpath": "/zynthian/zynthian-my-data/snapshots/000/My Snapshot 1.zss", # Full path and filename of last loaded snapshot
    "midi_profile_state": {  # Every ZYNTHIAN_MIDI_* environment variable at save time, with the prefix removed. All values are strings
        "ACTIVE_CHANNEL": "0", # "1" sends MIDI on the active chain's channel to all chains sharing that channel. "0" sends to the active chain only
        "USB_BY_PORT": "0", # "1" identifies USB MIDI devices by device name and physical USB port
        "PROG_CHANGE_ZS3": "1", # "1" MIDI program change loads a ZS3. "0" selects a preset instead
        "BANK_CHANGE": "0", # "1" MIDI bank select (CC0) changes the bank of the chain's first processor
        "FINE_TUNING": "440", # Global tuning reference in Hz (default 440)
        "FILTER_RULES": "", # MIDI filter rules script. Newlines are stored as a literal \n
        "CHANPRESS_CC": "0", # CC number that channel pressure is mapped to. "0" disables
        "NETWORK_ENABLED": "0", # "1" enables the QMidiNet network MIDI service
        "NETUMP_ENABLED": "0", # "1" enables the network UMP service
        "RTPMIDI_ENABLED": "0", # "1" enables the RTP-MIDI service (jackrtpmidid)
        "TOUCHOSC_ENABLED": "0", # "1" enables the TouchOSC to MIDI bridge (touchosc2midi)
        "BLE_ENABLED": "0", # "1" enables Bluetooth (BLE MIDI)
        "BLE_CONTROLLER": "", # Address of the Bluetooth controller to use. "" for default
        "AUBIONOTES_ENABLED": "0", # "1" enables the aubionotes audio to MIDI service
        "TRANSPORT_CLOCK_SOURCE": "Internal", # Transport clock source. Default "Internal"
        "PLAY_LOOP": "0", # "1" loops playback in the MIDI recorder
        "MASTER_CHANNEL": "0", # Master channel features MIDI channel, 1-based. "0" disables
        "MASTER_CHANGE_TYPE": "Roland", # Preset name for the master up/down messages. Read into config but not otherwise used
        "MASTER_PROGRAM_CHANGE_UP": "", # 4 hex digits, "#" = master channel. Loads the next snapshot program. "" disables
        "MASTER_PROGRAM_CHANGE_DOWN": "", # As MASTER_PROGRAM_CHANGE_UP, loads the previous snapshot program
        "MASTER_BANK_CHANGE_UP": "", # 6 hex digits (3-byte message), "#" = master channel. Selects the next snapshot bank. "" disables
        "MASTER_BANK_CHANGE_DOWN": "", # As MASTER_BANK_CHANGE_UP, selects the previous snapshot bank
        "MASTER_BANK_CHANGE_CCNUM": "0", # CC number on the master channel that selects the snapshot bank (code default 32)
        "MASTER_NOTE_CUIA": "", # Optional "note:CUIA" mappings separated by a literal \n. If absent, built-in defaults apply
        "port_names": {  # Friendly names indexed by port uid. Restored as the second alias of matching hardware ports
            "USB-1.1.1 CH345 MIDI IN": "VZ-1 IN",
            # ... More ports
        }
    },    
    "chains": {  # Dictionary of chains indexed by chain id (id=0 is main mixbus chain)
        "1": {  # Chain 1
            "title": "My first chain",  # Optional chain title
            "midi_chan": 0,  # Chain MIDI channel (may be None)
            "midi_thru": True, # True if chain passes MIDI
            "audio_thru": False, # True if chain passes audio
            "zmop_index": 1, # Index of zynmidirouter midi output (zmop) this chain uses
            "cc_route": [], # Optional list of MIDI CC to be routed directly to engine
            "slots": [  # List of slots in chain in serial slot order
                {  # Dictionary of processors in first slot
                    "1": "PT",  # Processor type indexed by processor id
                }, # ... more processors in this slot
            ], # ... More slots
            "zctrls": [ # List of pinned "Chain Controls"
                (3, "cutoff"), # Processor id, symbol
                # ... More zctrls
            ],
        }, # ... More chains
    },
    "zs3": {  # Dictionary of ZS3's indexed by chan/prog or ZS3-x
        "zs3-0": {  # ZS3 state when snapshot saved
            "title": "Last state",  # ZS3 title
            "note": "Capo 2, watch the MD",  # Optional ZS3 note, shown by the performance view
            "active_chain": 1, # Active chain id
            "active_phrase": 0, # Index of last selected phrase
            "restore_midi_learn": False, # Optional restore midi CC binding (Default: False)
            "processors": {  # Dictionary of processor settings
                "1": {  # Processor id:1
                    "restore": True, # Optional False to omit from processor parameters from restore (Default: True)
                    "bank_info": ["HB Steinway D", 0, "Grand Steinway D (Hamburg)", "D4:A", "HB Steinway Model D"], # Bank id
                    "bank_subdir_info": None, # Bank subdirectory info list
                    "preset_subdir_info": None, # Preset subdirectory info list
                    "current_screen_index": 0, # Index of control screen last shown
                    "preset_info": None,  # Preset id
                    "controllers": {  # Optional dictionary of controllers (overrides preset default value)
                        "volume": {  # Indexed by controller symbol
                            "value": 96,  # Controller value
                            "midi_cc_val1": 12, # Optional CC range minimum, value when controller value is 0
                            "midi_cc_val2": 96, # Optional CC range maximum, value when controller value is 127
                            "midi_cc_momentary_switch": 1, # Optional momentary toggle
                            "midi_cc_debounce": 1, # Optional toggle debounce
                            "midi_cc_mode": 0 # Optional CC control mode (0=abslute, 1-3=relative modes)
                        }, # ... More controllers
                    }, # ... Other parameters
                }, # ... Other controllers
            }, # ... Other processors
            "chains": {  # Dictionary of chain specific ZS3 config indexed by chain id
                "1": {  # Chain 1
                    "restore": True, # Optional False to omit chain from restore (default: True)
                    "midi_chan": 0, # Override chain MIDI channel
                    "midi_in": ["MIDI IN"], # List of chain jack MIDI input sources (may include aliases)
                    "midi_out": ["MIDI OUT"],# List of chain jack MIDI output destinations (may include aliases)
                    "audio_in": [0, 1], # List of index of physical input indices or zynmixer:send
                    "audio_out": [0, "system:playback"], # List of targets for chain routing: Chain id | jackport regex | [procid, input port name]
                    "note_low": 0,  # Optional lowest MIDI note chain responds to
                    "note_high": 127,  # Optional highest MIDI note chain responds to
                    "transpose_octave": 0,  # Optional octaves to transpose chain MIDI
                    "transpose_semitone": 0,  # Optional semitones to transpose chain MIDI
                },
            }, # ... Other chains
            "midi_capture": {  # Dictionary of midi input configuration mapped by port input uid
                "ttymidi:MIDI_in": {
                    "zmip_input_mode": True, # True if active chain mode enabled (stage mode), False for multitimbral
                    "zmip_system": True, # True to enable MIDI system messages (Not used)
                    "zmip_system_rt": True, # True to enable MIDI realtime system messages (Not used)
                    "disable_ctrldev": False,  # True to disable loading of controller device driver
                    "ctrldev_driver": "zynthian_ctrldev_launchkey_mini_mk3", # Name of controller device driver
                    "ctrldev_state": {}, # Optional dictionary, specific to each controller device driver
                    "routed_chains": [],  # List of chain zmops this input is routed to
                    "audio_in": [0, 1], # Optional list of audio inputs, e.g. for aubio
                    "midi_learn": {  # Dictionary of MIDI CC binding, indexed by 24-bit hex encoded (chain (ff for global), MIDI chan (ff for any channel), CC)
                        "ff0021": [  # List of control bindings to this CC
                            [
                                1, # Processor id
                                "volume" # Controller symbol
                            ]
                        ], # ... Other controllers
                    } # ... Other bindings
                }, # ... Other devices
                "zynmidi": { # Internal / GUI MIDI config
                    "midi_learn": { # Same as physical MIDI input midi_learn (not implemented)
                    }
                }
            },
            "global": {  # Dictionary of global params settable by zs3 indexed by param name
                "midi_transpose": 0,  # Semitones to globally transpose
                "zctrl_x": [0, "volume"], # Optional mapping of x-axis controller [proc_id, symbol]
                "zctrl_y": [0, "cutoff"], # Optional mapping of y-axis controller [proc_id, symbol]
                "zynaptik": { # Optional zynaptik configuration
                    "cvin_volts_octave": 1.0, # CV input volts per octave
                    "cvin_note0": 0, # CV input note 0 
                    "cvout_volts_octave": 1.0, # CV output volts per octave
                    "cvout_note0": 0 # CV output note 0
                },
                "clock_outputs": [ # List of MIDI output ports to send MIDI clock
                    "ttymidi:MIDI_out",
                    "USB:2.2/APC40 mkII OUT 1",
                    # ... Other ports
                ],
                "clock_source": None, # Name of MIDI input acting as MIDI clock source. None for internal.
                "zynseq_excluded_inputs": [], # List of MIDI input port names not feeding zynseq
            }
        },
        "1/2": {},  # ZS3 for channel 1, program change 2
        "zs3-1": {},  # Manually saved ZS3 without assigned program change
    }, # ... Other ZS3
    "last_zs3_id": "zs3-1", # Id of the last recalled ZS3
    "zynseq": {
        "tempo": 120.0, # Default tempo in BPM
        "bpb": 4, # Default beats per bar (time signature)
        "scene": 0, # Selected scene when saved
        "patns": { # Map of patterns, indexed by pattern id
            "1": { # Pattern id
                "steps": 16, # Steps in pattern
                "beats": 4, # Beats in pattern
                "scale": 0, # Index of scale to use for this pattern
                "tonic": 0, # Root note for scale
                "refNote": 51,
                "zoom": 0, # Grid zoom
                "ccnum": [False, True, ...], # List of 128 flags indicating whether to interpolate CC
                "quantize": 0, # Amount to quantize
                "swingDiv": 1, # Swing divisor
                "swing": 0.0, # Amount of swing to apply to pattern
                "humanTime": 0.0, # Variation in timing feel
                "humanVel": 0.0, # Variation in velocity feel
                "chance": 100, # Probability % of notes within pattern playing
                "events": [ # List of events in the pattern
                    [ # List of event parameters (use list for optimisation)
                        0, # Step within pattern
                        0.0, # Offset from start of step
                        1.0, # Duration of event
                        144, # MIDI command
                        60, # MIDI value 1 at start of event
                        60, # MIDI value 1 at end of event
                        100, # MIDI value 2 at start of event
                        0, # MIDI value 2 at end of event
                        0, # Quantity of stutters
                        1, # Stutter velocity speed FX value
                        0, # Note stutter ramp FX value
                        100, # Probability % of event triggering
                        1, # Play frequency
                        100, # Stutter play chance (%)
                        1 # Stutter frequency
                    ], # ... Other events
                ]
            }, # ... Other patterns
        },
        "scenes": [ # List of scenes, indexed by scene id
            { # First scene
                "name": "Scene 1", # Optional scene name
                "phrases": [ # List of phrases, indexed by phrase number
                    { # First phrase
                        "name": "A", # Phrase name
                        "mode": 4, # Phrase play mode
                        "bpb": 4, # Beats per bar (time signature) override
                        "tempo": 0, # Tempo override 0=no override
                        "repeat": 1, # Quantity of repeats
                        "followAction": 0, # Follow action
                        "followParam": 0, # Follow action param
                        "followRepeat": 0, # Quantity of times a follow action is performed, e.g. loops
                        "playFlags": 0, # Bitwise flags indicating which follow loops should be skipped
                        "state": 0, # Play state (when snapshot saved)
                        "sequences": [ # List of sequences in phrase
                            {
                                "mode": 4, # Sequence play mode
                                "group": 0, # Mutex group (0..15, Chain MIDI channel else multi-channel)
                                "name": "1", # Sequence name
                                "repeat": 1, # Quantity of repeats
                                "followAction": 0, # Follow action
                                "followParam": 0, # Follow action param
                                "state": 0, # Play state (when snapshot saved)
                                "tracks": [ # List of tracks in sequence
                                    {
                                        "chan": 0, # MIDI channel
                                        "output": 0, # Jack output
                                        "map": 0, # Key map
                                        "patns": { # Indexed by relative start time within sequence
                                            "0": 3, # Pattern id
                                            # ... Other patterns
                                        }
                                    }, # ... Other tracks
                                ],
                                "nBeats": 4, # Number of beats in sequence
                                "nEvents": 0, # Number of events in sequence
                                "timebase": [ # List of timebase events
                                    { # Event
                                        "bar": 1, # Measure or bar of event
                                        "tick": 0, # Tick within measure
                                        "type": 0, # Event type, e.g. tempo
                                        "value": 80 # Event value
                                    },
                                    # ... Other timebase events
                                ]
                            }, # ... Other sequences
                        ],
                    }, # .. Other phrases
                ],
            }, # Other scenes
        ]
    },
    "gui": { # Optional GUI configuration
        "pinned_chains": 1 # Quantity of chains pinned to right edge (including main mixbus)
    },
    "engine_config": { # Optional extended engine configuration, indexed by engine id
        "1": {"key": "value"} # Engine specific dictionary
    }
}
