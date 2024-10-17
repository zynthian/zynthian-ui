# -*- coding: utf-8 -*-
# ****************************************************************************
# ZYNTHIAN PROJECT: Zynthian Legacy Snapshots
#
# Legacy snapshots convertion
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
#
# ****************************************************************************
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
# ****************************************************************************

from json import JSONDecoder
from zyngine.zynthian_chain_manager import zynthian_chain_manager
import logging

SNAPSHOT_SCHEMA_VERSION = 1


class zynthian_legacy_snapshot:

    def __init__(self):
        self.engine_info = zynthian_chain_manager.get_engine_info()

    def convert_file(self, fpath):
        """Converts legacy snapshot to current version

        fpath : Snapshot filename including path
        Returns : Dictionary representing zynthian state model
        """

        try:
            with open(fpath, "r") as fh:
                json = fh.read()
                snapshot = JSONDecoder().decode(json)
        except Exception as e:
            logging.error("Can't load snapshot '%s': %s" % (fpath, e))
            return None

        return self.convert_state(snapshot)

    def convert_state(self, snapshot):
        """Converts a legacy snapshot to current version

        snapshot : Legacy snapshot as dictionary
        Returns : Current state model as dictionary
        """

        if "schema_version" in snapshot:
            return snapshot
        snapshot = self.convert_old_legacy(snapshot)
        self.jackname_counters = {}
        self.aeolus_count = 0
        self.setBfree_count = 0

        state = {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "midi_profile_state": {},
            'chains': {},
            "zs3": {
                "zs3-0": {
                    "title": "Last state",
                    "chains": {},
                    "processors": {},
                    "mixer": {},
                },
            },
            "engine_config": {},
            "audio_recorder_armed": [],
            "zynseq_riff_b64": "",
            "alsa_mixer": {},
            "zyngui": {
                "processors": {}
            }
        }

        try:
            state["zs3"]["zs3-0"]["active_chain"] = int(
                f"{snapshot['index']:02d}") + 1
        except:
            pass

        try:
            state["last_snapshot_fpath"] = snapshot["last_snapshot_fpath"]
        except:
            pass

        try:
            state["midi_profile_state"] = snapshot["midi_profile_state"]
            single_active_channel = state["midi_profile_state"]["SINGLE_ACTIVE_CHANNEL"]
        except:
            single_active_channel = True

        try:
            for id, value in snapshot["extended_config"].items():
                if value:
                    state["engine_config"][id] = value
        except:
            pass

        try:
            state["audio_recorder_armed"] = snapshot["audio_recorder_armed"]
        except:
            pass

        try:
            state["zynseq_riff_b64"] = snapshot["zynseq_riff_b64"]
        except:
            pass

        note_range_state = []
        if "note_range" in snapshot:
            if len(snapshot["note_range"]) == 16:
                note_range_state = snapshot["note_range"]

        # Get processors
        processors = {}
        chains = {}
        global_midi_cc = {}

        for proc_id, layer in enumerate(snapshot["layers"]):
            if layer['engine_nick'] == "AI":
                continue
            if layer['engine_nick'] == "MX":
                try:
                    state["alsa_mixer"]["controllers"] = layer["controllers_dict"]
                except:
                    pass
                continue

            midi_chan = layer["midi_chan"]
            chain_id = midi_chan + 1
            if chain_id > 16:
                chain_id = 0
            if chain_id not in chains:
                chains[chain_id] = {
                    "midi_processors": [],  # Temporary list of processors in chain - used to build slots
                    "synth_processors": [],  # Temporary list of processors in chain - used to build slots
                    "audio_processors": [],  # Temporary list of processors in chain - used to build slots
                    "mixer_chan": midi_chan,
                    "midi_chan": None,
                    "current_processor": 0,
                    "slots": []
                }
                chain_state = {
                    "audio_out": [],
                    "midi_thru": False,
                    "audio_in": [],
                    "audio_thru": False
                }
                if midi_chan < 16:
                    chains[chain_id]["midi_chan"] = midi_chan
                    chain_state["note_low"] = note_range_state[midi_chan]["note_low"]
                    chain_state["note_high"] = note_range_state[midi_chan]["note_high"]
                    chain_state["transpose_octave"] = note_range_state[midi_chan]["octave_trans"]
                    chain_state["transpose_semitone"] = note_range_state[midi_chan]["halftone_trans"]
                else:
                    chain_id = 0
                chain_state["midi_cc"] = {}

                if "controllers_dict" in layer:
                    for symbol, cfg in layer["controllers_dict"].items():
                        try:
                            midi_learn_cc = cfg.pop("midi_learn_cc")
                            if "midi_learn_chan" in cfg:
                                midi_learn_chan = cfg.pop("midi_learn_chan")
                                if midi_learn_chan not in global_midi_cc:
                                    global_midi_cc[midi_learn_chan] = {}
                                if midi_learn_cc not in global_midi_cc[midi_learn_chan]:
                                    global_midi_cc[midi_learn_chan][midi_learn_cc] = [
                                    ]
                                global_midi_cc[midi_learn_chan][midi_learn_cc].append(
                                    (proc_id, symbol))
                                # TODO: Add global midi learn to midi capture
                            # TODO: Do not add global midi learn to chain
                            if midi_learn_cc not in chain_state["midi_cc"]:
                                chain_state["midi_cc"][midi_learn_cc] = []
                            chain_state["midi_cc"][midi_learn_cc].append(
                                (proc_id, symbol))
                        except:
                            pass
                # Save chain_state in state data struct
                state["zs3"]["zs3-0"]["chains"][chain_id] = chain_state

            jackname = self.build_jackname(layer["engine_name"], midi_chan)
            try:
                for input in snapshot["audio_capture"][jackname]:
                    if input.startswith("system:capture_"):
                        state["zs3"]["zs3-0"]["chains"][chain_id]["audio_in"].append(
                            int(input.split("_")[1]))
            except:
                pass

            # Get engine info
            try:
                info = self.engine_info[layer['engine_nick']]
            except:
                info = {}
            if info and not jackname.startswith("audioin"):
                if info["TYPE"] == "Audio Effect":
                    chains[chain_id]["audio_processors"].append(jackname)
                elif info["TYPE"] == "MIDI Tool":
                    chains[chain_id]["midi_processors"].append(jackname)
                else:
                    chains[chain_id]["synth_processors"].append(jackname)
                if jackname.startswith("aeolus"):
                    layer["bank_info"] = ("General", 0, "General")
                    layer["preset_info"][0] = layer["preset_info"][2]
                processors[jackname] = {
                    "id": proc_id,
                    "info": info,
                    "nick": layer["engine_nick"],
                    "midi_chan": midi_chan,
                    "bank_info": layer["bank_info"],
                    "preset_info": layer["preset_info"],
                    "controllers": layer["controllers_dict"],
                }
                if not layer["bank_info"]:
                    processors[jackname]["bank_info"] = [
                        "None", None, "None", None]
                if not layer["preset_info"]:
                    processors[jackname]["preset_info"] = layer["preset_index"]

                # Add zyngui specific stuff (should maybe be in GUI code?)
                state["zyngui"]["processors"][proc_id] = {}
                if "show_fav_presets" in layer:
                    state["zyngui"]["processors"][proc_id]["show_fav_presets"] = layer["show_fav_presets"]
                if "active_screen_index" in layer and layer["active_screen_index"] >= 0:
                    state["zyngui"]["processors"][proc_id]["active_screen_index"] = layer["active_screen_index"]

        # Create map of audio only channels for 'sidechaining'
        audio_only_chains = {}
        for chain_id, chain in chains.items():
            if len(chain["midi_processors"]) + len(chain["synth_processors"]) > 0 or len(chain["audio_processors"]) == 0:
                continue
            audio_only_chains[chain_id] = None

        aeolus_done = False
        setBfree_done = False
        for chain_id, chain in chains.items():
            audio_out = []
            midi_out = []
            # Add audio slots
            proc_count = len(chain["audio_processors"])
            if proc_count > 0:
                slot = []
                # Populate last slot
                for proc in chain["audio_processors"]:
                    if proc in snapshot["audio_routing"]:
                        last_slot = True
                        route = snapshot["audio_routing"][proc]
                        for dst in route:
                            if dst in chain["audio_processors"]:
                                last_slot = False
                                break  # processor feeds another processor so not in last slot
                        if last_slot:
                            slot.append(proc)
                            audio_out = route
                            proc_count -= 1
                    else:
                        logging.warning(
                            f"No audio routing info for processor {proc} in chain {chain_id}!")

                if slot:
                    chain["slots"].insert(0, slot)

                # Populate rest of slots
                while proc_count > 0:
                    slot = []
                    for proc in chain["audio_processors"]:
                        if proc in snapshot["audio_routing"]:
                            route = snapshot["audio_routing"][proc]
                            for dst in route:
                                if dst in chain["slots"][0]:
                                    slot.append(proc)
                                    if not audio_out:
                                        audio_out = route
                                    proc_count -= 1
                                    if proc_count < 1:
                                        break
                        else:
                            proc_count -= 1
                            logging.warning(
                                f"No audio routing info for processor {proc} in chain {chain_id}!")

                        if proc_count < 1:
                            break

                    if slot:
                        chain["slots"].insert(0, slot)

            # Add synth slot
            if chain["synth_processors"]:
                chain["slots"].insert(0, chain["synth_processors"])
                if not chain["audio_processors"]:
                    try:
                        proc_name = chain["synth_processors"][0]
                        if (proc_name == "aeolus" and aeolus_done) or (proc_name == "setBfree" and setBfree_done):
                            chain["mixer_chan"] = None
                        else:
                            audio_out = snapshot["audio_routing"][chain["synth_processors"][0]]
                            if proc_name == "aeolus":
                                aeolus_done = True
                            if proc_name == "setBfree":
                                setBfree_done = True
                    except:
                        pass  # MIDI only chains for synth engines should be ignored

            # Add MIDI slots
            proc_count = len(chain["midi_processors"])
            if proc_count > 0:
                slot = []
                # Populate last slot
                for proc in chain["midi_processors"]:
                    last_slot = True
                    route = snapshot["midi_routing"][proc]
                    for dst in route:
                        if dst in chain["midi_processors"]:
                            last_slot = False
                            break  # processor feeds another processor so not in last slot
                    if last_slot:
                        slot.append(proc)
                        if not chain["synth_processors"]:
                            midi_out = route
                        proc_count -= 1
                if slot:
                    chain["slots"].insert(0, slot)
                while proc_count > 0:
                    slot = []
                    for proc in chain["midi_processors"]:
                        route = snapshot["midi_routing"][proc]
                        for dst in route:
                            if dst in chain["slots"][0]:
                                slot.append(proc)
                                proc_count -= 1
                                if proc_count < 1:
                                    break
                        if proc_count < 1:
                            break
                    if slot:
                        chain["slots"].insert(0, slot)

            if chain["midi_processors"] and not chain["synth_processors"] and not chain["audio_processors"]:
                state["zs3"]["zs3-0"]["chains"][chain_id]["midi_thru"] = True
                chain["mixer_chan"] = None
                audio_out = []
            if not chain["midi_processors"] and not chain["synth_processors"]:
                state["zs3"]["zs3-0"]["chains"][chain_id]["audio_thru"] = True
                chain["midi_chan"] = None
                if chain["mixer_chan"] > 16:
                    # TODO: Get max channels from mixer
                    chain["mixer_chan"] = 16

            # Fix-up audio outputs
            if chain_id == 0:
                state["zs3"]["zs3-0"]["chains"][chain_id]["audio_out"].append(
                    "system:playback_[1,2]$")
            else:
                for out in audio_out:
                    if out == "mixer":
                        state["zs3"]["zs3-0"]["chains"][chain_id]["audio_out"].append(
                            0)
                    elif isinstance(out, int):
                        state["zs3"]["zs3-0"]["chains"][chain_id]["audio_out"].append(
                            out)

            state["zs3"]["zs3-0"]["chains"][chain_id]["midi_out"] = midi_out
            fixed_slots = []
            for slot in chain["slots"]:
                fixed_slot = {}
                for processor in slot:
                    fixed_slot[f"{processors[processor]['id']}"] = f"{processors[processor]['nick']}"
                if fixed_slot:
                    fixed_slots.append(fixed_slot)
            chain["slots"] = fixed_slots

            if chain_id in audio_only_chains:
                audio_only_chains[chain_id] = chain['audio_processors'][0]

            chain.pop("midi_processors")
            chain.pop("synth_processors")
            chain.pop("audio_processors")

        # Fix main chain
        try:
            chains[0] = chains.pop(257)
            chains[0]["midi_chan"] = None
            # chains[0]["mixer_chan"] = None
        except:
            pass

        state["chains"] = chains

        # ZS3
        state["zs3"]["zs3-0"]["mixer"] = {}
        try:
            if isinstance(snapshot["mixer"], dict):
                state["zs3"]["zs3-0"]["mixer"] = snapshot["mixer"]
            else:
                for i, mixer_ch in enumerate(snapshot["mixer"]):
                    state["zs3"]["zs3-0"]["mixer"][f"chan_{i:02d}"] = mixer_ch
        except:
            pass

        for proc in processors.values():
            state["zs3"]["zs3-0"]["processors"][proc["id"]] = {
                "bank_info": proc["bank_info"],
                "preset_info": proc["preset_info"],
                "controllers": proc["controllers"]
            }

        next_id = 1
        if "learned_zs3" in snapshot:
            for zs3 in snapshot["learned_zs3"]:
                # Ignore channel if "stage mode" is enabled
                if not single_active_channel and "midi_learn_chan" in zs3:
                    midi_chan = zs3["midi_learn_chan"]
                else:
                    midi_chan = None
                if "midi_learn_prognum" in zs3:
                    midi_pgm = zs3["midi_learn_prognum"]
                else:
                    midi_chan = None
                    midi_pgm = None
                if midi_pgm is None:
                    zs3_id = f"zs3-{next_id}"
                    next_id += 1
                elif midi_chan is None:
                    zs3_id = f"*/{midi_pgm}"
                else:
                    zs3_id = f"{midi_chan}/{midi_pgm}"

                zs3_title = zs3["zs3_title"]
                if zs3_title == "New ZS3":
                    zs3_title = zs3_id

                state["zs3"][zs3_id] = {
                    "title": zs3_title,
                    "active_chain": int(zs3['index']) + 1,
                    "chains": {},
                    "processors": {},
                    "midi_learn_cc": {
                        "absolute": {},
                        "chain": {}
                    },
                    "mixer": zs3["mixer"]
                }
                self.jackname_counters = {}
                self.aeolus_count = 0
                self.setBfree_count = 0
                for layer in zs3["layers"]:
                    jackname = self.build_jackname(
                        layer["engine_name"], layer["midi_chan"])
                    if jackname in processors:
                        if jackname.startswith("aeolus"):
                            layer["bank_info"] = ("General", 0, "General")
                            layer["preset_info"][0] = layer["preset_info"][2]
                        proc = processors[jackname]
                        state["zs3"][zs3_id]["processors"][proc["id"]] = {
                            "bank_info": layer["bank_info"],
                            "preset_info": layer["preset_info"],
                            "controllers": layer["controllers_dict"]
                        }

                for chain_id, chain in chains.items():
                    chain_state = {
                        # "audio_out": [],
                        # "midi_thru": False,
                        # "audio_in": [],
                        # "audio_thru": False,
                        # "midi_cc": {}
                    }
                    midi_chan = chain["midi_chan"]
                    if isinstance(midi_chan, int) and midi_chan < 16:
                        chain_state["note_low"] = note_range_state[midi_chan]["note_low"]
                        chain_state["note_high"] = note_range_state[midi_chan]["note_high"]
                        chain_state["transpose_octave"] = note_range_state[midi_chan]["octave_trans"]
                        chain_state["transpose_semitone"] = note_range_state[midi_chan]["halftone_trans"]
                    # Save chain_state in state data struct
                    state["zs3"][zs3_id]["chains"][chain_id] = chain_state

        # Fix ZS3 mixer MIDI learn
        for zs3 in state["zs3"].values():
            if "mixer" in zs3:
                zs3["mixer"]["midi_learn"] = {}
                for strip, config in zs3["mixer"].items():
                    if strip == "main":
                        strip_id = 16  # TODO: Get actual main mixer strip index
                    else:
                        try:
                            strip_id = int(strip.split('_')[1])
                            if strip_id > 16:
                                strip_id = 16
                        except:
                            continue
                    for symbol, params in config.items():
                        try:
                            if 'midi_learn_chan' in params:
                                chan = params.pop('midi_learn_chan')
                            else:
                                chan = None
                            if 'midi_learn_cc' in params:
                                cc = params.pop('midi_learn_cc')
                            else:
                                cc = None
                            if cc is not None and chan is not None:
                                zs3["mixer"]["midi_learn"][f"{chan},{cc}"] = [
                                    strip_id, symbol]
                        except:
                            pass
                        try:
                            config[symbol] = config[symbol]["value"]
                        except:
                            pass

        # Fix audio routing
        for id, zs3 in state["zs3"].items():
            if "chains" in zs3:
                for chain_id, chain in zs3["chains"].items():
                    """
                    mout = False
                    out = []
                    for aout in chain["audio_out"]:
                        try:
                            out.append(processors[aout]['id'])
                        except:
                            if not aout.startswith("system:playback_"): 
                                out.append(aout)
                            else:
                                mout = True
                    chain["audio_out"] = out.copy()
                    if mout and "mixer" not in chain["audio_out"]:
                        chain["audio_out"].append("mixer")
                    """
                    if chain_id == 0:
                        if state["chains"][0]["slots"]:
                            chain["audio_in"] = ["zynmixer:send"]
                        else:
                            chain["audio_in"] = []

                    # TODO: Handle multiple outputs... Identify single common processor chain to move to main chain.

        # Emulate clone by setting destination midi channel to source midi channel
        if "clone" in snapshot:
            active_midi_channel = "0"
            for clone_from_chan, clone_cfg in enumerate(snapshot["clone"]):
                for clone_to_chan, cfg in enumerate(clone_cfg):
                    try:
                        if cfg["enabled"]:
                            state["chains"][clone_to_chan +
                                            1]["midi_chan"] = state["chains"][clone_from_chan + 1]["midi_chan"]
                            active_midi_channel = "1"
                    except Exception as e:
                        logging.warning(
                            "Failed to emulate cloning from {clone_from_chan} to {clone_to_chan}")

            state["midi_profile_state"]["ACTIVE_CHANNEL"] = active_midi_channel

        return state

    def build_jackname(self, engine_name, midi_chan):
        """Build the legacy jackname for the engine name

        engine_name : Engine type name
        midi_chan : Engine MIDI channel
        Returns : Jackname as string
        """

        if engine_name.startswith("Jalv/"):
            name = engine_name[5:]
        else:
            name = engine_name

        if name == "LinuxSampler":
            if name not in self.jackname_counters:
                self.jackname_counters[name] = 0
            jackname = f"LinuxSampler:CH{self.jackname_counters[name]}_"
            self.jackname_counters[name] += 1
        elif name == "Audio Input":
            jackname = f"audioin-{midi_chan:02d}"
        elif name == "ZynAddSubFX":
            if name not in self.jackname_counters:
                self.jackname_counters[name] = 0
            jackname = f"zynaddsubfx:part{self.jackname_counters[name]}/"
            self.jackname_counters[name] += 1
        elif name == "FluidSynth":
            if name not in self.jackname_counters:
                self.jackname_counters[name] = 0
            jackname = f"fluidsynth:(l|r)_{self.jackname_counters[name]:02d}"
            self.jackname_counters[name] += 1
        elif name == "Aeolus":
            if self.aeolus_count:
                jackname = f"aeolus{self.aeolus_count}"
            else:
                jackname = "aeolus"
            self.aeolus_count += 1
        elif name == "setBfree":
            if self.setBfree_count:
                jackname = f"setBfree{self.setBfree_count}"
            else:
                jackname = "setBfree"
            self.setBfree_count += 1
        elif name.startswith("Pianoteq"):
            jackname = "Pianoteq"
        elif name == "SooperLooper":
            jackname = "sooperlooper"
        else:
            if name in ["Sfizz"]:
                name = name.lower()
            if name not in self.jackname_counters:
                self.jackname_counters[name] = 0
            jackname = f"{name.replace(' ', '_')}-{self.jackname_counters[name]:02d}"
            self.jackname_counters[name] += 1

        return jackname

    def convert_old_legacy(self, state):
        """Convert from older legacy snapshot format state
        state : Dictionary containing state model
        Returns : State fixed to newer legacy format
        """

        newer = True
        if "layers" in state:
            for layer in state["layers"]:
                if "zs3_list" in layer:
                    newer = False
                    break
        if newer:
            return state

        zs3_index = 0
        for midi_chan in range(0, 16):
            for prog_num in range(0, 128):
                lstates = [None] * len(state['layers'])
                note_range = [None] * 16
                root_layer_index = None
                for li, lss in enumerate(state['layers']):
                    if 'zs3_list' in lss and midi_chan == lss['midi_chan']:
                        lstate = lss['zs3_list'][prog_num]
                        if not lstate:
                            continue
                        try:
                            root_layer_index = self.root_layers.index(
                                self.layers[li])
                        except:
                            pass
                        lstate['engine_name'] = lss['engine_name']
                        lstate['engine_nick'] = lss['engine_nick']
                        lstate['engine_jackname'] = self.layers[li].engine.jackname
                        lstate['midi_chan'] = midi_chan
                        lstate['show_fav_presets'] = lss['show_fav_presets']
                        if 'active_screen_index' in lstate:
                            lstate['current_screen_index'] = lstate['active_screen_index']
                            del lstate['active_screen_index']
                        if 'note_range' in lstate:
                            # TODO: Move to ZS3
                            if lstate['note_range']:
                                note_range[midi_chan] = lstate['note_range']
                            del lstate['note_range']
                        lstates[li] = lstate

                if root_layer_index is not None:
                    zs3_new = {
                        'index': root_layer_index,
                        'layers': lstates,
                        'note_range': note_range,
                        'zs3_title': "Legacy ZS3 #{}".format(zs3_index + 1),
                        'midi_learn_chan': midi_chan,
                        'midi_learn_prognum': prog_num
                    }
                    self.learned_zs3.append(zs3_new)
                    # logging.debug("ADDED LEGACY ZS3 #{} => {}".format(zs3_index, zs3_new))
                    zs3_index += 1

        return state
