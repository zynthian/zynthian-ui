# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian State Model Schema
# 
# Copyright (C) 2022-2023 Fernando Moyano <jofemodo@zynthian.org>
#                    Brian Walton <riban@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

ZynthianState = {
    "schema_version": 1, # Version of state (snapshot) model
    "last_snapshot_fpath": "/zynthian/zynthian-my-data/snapshots/000/My Snapshot 1.zss", # Full path and filename of last loaded snapshot
    "midi_profile_state": { # MIDI Profile TODO: Document midi profile
		"MASTER_BANK_CHANGE_UP": "",
		"SYS_ENABLED": "1",
		"MASTER_PROGRAM_CHANGE_DOWN": "",
		"SINGLE_ACTIVE_CHANNEL": "0",
		"RTPMIDI_ENABLED": "0",
		"TOUCHOSC_ENABLED": "0",
		"PORTS": "DISABLED_IN=\\nENABLED_OUT=ttymidi:MIDI_out,QmidiNet:in_1\\nENABLED_FB=",
		"MASTER_CHANNEL": "0",
		"NETWORK_ENABLED": "0",
		"FILTER_RULES": "",
		"PROG_CHANGE_ZS3": "1",
		"MASTER_PROGRAM_CHANGE_UP": "",
		"BANK_CHANGE": "0",
		"CC_AUTOMODE": "0",
		"MASTER_BANK_CHANGE_CCNUM": "0",
		"MASTER_BANK_CHANGE_DOWN": "",
		"PRESET_PRELOAD_NOTEON": "1",
		"AUBIONOTES_ENABLED": "0",
		"FINE_TUNING": "440",
		"MASTER_PROGRAM_CHANGE_TYPE": "Custom",
		"PLAY_LOOP": "0",
		"FILTER_OUTPUT": "0",
        "port_names": { # Dictionary of MIDI port friendly names indexed by port uid
            "USB-1.1.1 CH345 MIDI IN": "VZ-1 IN", # Friendly name mapped by uid
            #... More ports
        }
    },
    "chains": { # Dictionary of chains indexed by chain ID
        "1": { # Chain 1
            "title": "My first chain", # Chain title (optional)
            "mixer_chan": 0, # Chain audio mixer channel (may be None)
            "midi_chan": 0, # Chain MIDI channel (may be None)
            "current_processor": 0, # Index of the processor last selected within chain (Should this go in GUI section?)
            "slots": [ # List of slots in chain in serial slot order
                { # Dictionary of processors in first slot
                    "1": "PT", # Processor type indexed by processor id
                    #... more processors in this slot
                },
                #... More slots
            ],
            "fader_pos": 1 # Index of slot where fader is (divides pre/post fader audio effects)
        }
    },
    "zs3": { # Dictionary of ZS3's indexed by chan/prog or ZS3-x
        "zs3-0": { # ZS3 state when snapshot saved
            "title": "Last state", # ZS3 title
            "active_chain": "01", # Active chain ID (optional, overides base value)
            "processors": { # Dictionary of processor settings
                "1": { # Processor id:1
                    "bank_info": ["HB Steinway D", 0, "Grand Steinway D (Hamburg)", "D4:A", "HB Steinway Model D"], # Bank ID
                    "preset_info": None, # Preset ID
                    "controllers": { # Dictionary of controllers (optional, overrides preset default value)
                        "volume": { # Indexed by controller symbol
                            "value": 96, # Controller value
                        },
                    },
                    #... Other controllers
                }
            },
            #... Other processors
            "mixer": { # Dictionary of audio mixer configuration (optional, overrides base value)
                "chan_00": { # Indexed by mixer channel / strip (or "main")
                    "level": 0.800000011920929, # Fader value (optional, overrides base value)
                    "balance": 0.5, # Balance/pan state (optional, overrides base value)
                    "mute": 0, # Mute state (optional, overrides base value)
                    "solo": 0, # Solo state (optional, overrides base value)
                    "mono": 0, # Mono state (optional, overrides base value)
                    "phase": 0, # Phase reverse state (optional, overrides base value)
                },
                #... Other mixer strips
                "midi_learn": { # Mixer MIDI learn
                    "chan,cc": "graph_path", # graph_path [strip index, param symbol] mapped by "midi chan, midi cc"
                    #... Other MIDI learn configs
                }
            },
            "chains": { # Dictionary of chain specific ZS3 config indexed by chain ID
                "01": { # Chain 01
                    "midi_in": ["MIDI IN"], # List of chain jack MIDI input sources (may include aliases)
                    "midi_out": ["MIDI OUT"], # List of chain jack MIDI output destinations (may include aliases)
                    "midi_thru": False, # True to allow MIDI pass-through when MIDI chain empty
                    "audio_in": [0,1], # List of index of physical input indicies or zynmixer:send
                    "audio_out": [0,"system:playback"], # Targets for chain routing: Chain id | jackport regex | [procid, input port name]
                    "audio_thru": False, # True to allow audio pass-through when audio chain empty
                    "note_low": 0, # Lowest MIDI note chain responds to
                    "note_high": 127, # Higheset MIDI note chain responds to
                    "transpose_octave": 0, # Octaves to transpose chain MIDI
                    "transpose_semitone": 0, # Semitones to transpose chain MIDI
                    "midi_cc": { # Dictionary of MIDI mapping, indexed by CC number
                        "7": [ # List of controller configs
                            ["2", "volume"], # Controller configs [proc_id, symbol]
                            #... Other controllers mapped to this CC
                        ],
                        #... Other CC mapped to this chain
                    }
                },
                #... Other chains
            },
            "midi_capture": { # Dictionary of midi input configuration mapped by port input uid 
                "ttymidi:MIDI_in": { # 
                    "zmip_input_mode": 1, # 1 if active chain mode enabled (stage mode), 0 for multitimbral
                    "ctrldev_load": 0, # 1 to attempt loading controller device driver
                    "routed_chains": [], # List of chain zmops this input is routed to
                    "audio_in": [0,1], # List of audio inputs, e.g. for aubio (optional)
                    "midi_cc": { # Map of MIDI CC mapping, indexed by MIDI channel
                        "0": { # Map of controls, indexed by CC number
                            "121": [ # List of controller configs
                                [1, "volume"], # Controller config [proc_id, symbol]
                                #... Other controllers
                            ],
                            #... Other CCs
                        },
                        #... Other MIDI channels
                    }
                }
            },
        },
        "1/2": {}, # ZS3 for channel 1, program change 2
        "zs3-1": {}, # Manually saved ZS3 without assigned program change
        #... Other ZS3
    },
    "engine_config" : { # Engine specific configuration (global for all processor instances of engine
        "MX": None, # ALSA mixer configuration
        "PT": None, # Pianoteq configuration
        #... Other engines
    },
    "audio_recorder_armed": [0, 3], # List of audio mixer strip indicies armed for multi-track audio recording
    "zynseq_riff_b64": "dmVycwAA...", # Binary encoded RIFF data for step sequencer patterns, sequences, etc.
    "alsa_mixer": { # Indexed by processor ID
        "controllers": { # Dictionary of controllers
            "Digital_0": { # Indexed by control symbol
                "value": 100 # Controller value
            }, #... Other controllers
        }
    },
    "zyngui": { # Optional UI specific configuration
        "processors": { # Processor specific config
            "1": { # Indexed by processor id
                "show_fav_presets": False, # True if presets displayed
                "current_screen_index": 8 # Index of last selected controller view page
            }
        }
    }
}