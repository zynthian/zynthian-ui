from json import JSONDecoder
from zyngine import zynthian_state_manager
import logging

SNAPSHOT_SCHEMA_VERSION = 1

class zynthian_legacy_snapshot:

    def __init__(self):
        pass

    def convert_file(self, fpath):
        """Converts legacy snapshot to current version
        
        fpath : Snapshot filename including path
        engine_info : Engine info from chain manager
        Returns : Dictionary representing zynthian state model
        """

        try:
            with open(fpath,"r") as fh:
                json = fh.read()
                snapshot = JSONDecoder().decode(json)
        except Exception as e:
            logging.error("Can't load snapshot '%s': %s" % (fpath, e))
            return None
        
        return self.convert_state(snapshot)

    def convert_state(self, snapshot, engine_info):
        """Converts a legacy snapshot to current version
        
        snapshot : Legacy snapshot as dictionary
        Returns : Current state model as dictionary
        """

        self.jackname_counters = {}

        state = {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "midi_profile_state": {},
            'chains': {},
            "zs3": {
                "zs3-0": {
                    "title": "Last state",
                    "processors": {
                    },
                    "mixer": {}
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

        if "index" in snapshot and snapshot["index"] >= 0:
            state["zs3"]["zs3-0"]["active_chain"] = f"{snapshot['index']:02d}"

        try:
            state["last_snapshot_fpath"] = snapshot["last_snapshot_fpath"]
        except:
            pass

        try:
            state["midi_profile_state"] = snapshot["midi_profile_state"]
        except:
            pass

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

        #TODO: Add zs3

        # Get processors
        processors = {}
        chains = {}
        proc_id = 1
        for l in snapshot["layers"]:
            if l['engine_nick'] == "MX":
                try:
                    state["alsa_mixer"]["controllers"] = l["controllers_dict"]
                except:
                    pass
                continue
            elif l["engine_name"].startswith("Jalv/"):
                type = "JV"
                name= l["engine_name"][5:]
            else:
                type = l["engine_nick"]
                name = l["engine_name"]

            try:
                info = engine_info[l['engine_nick']]
            except:
                info = []
            midi_chan = l["midi_chan"]
            jackname = self.build_jackname(name, midi_chan)
            chain_id = f"{midi_chan:02d}"
            if chain_id not in chains:
                chains[chain_id] = {
                    "midi_processors": [], # Temporary list of processors in chain - used to build slots
                    "synth_processors": [], # Temporary list of processors in chain - used to build slots
                    "audio_processors": [], # Temporary list of processors in chain - used to build slots
                    "mixer_chan": midi_chan,
                    "midi_chan": midi_chan,
                    "midi_in": ["MIDI IN"],
                    "midi_out": ["MIDI OUT"],
                    "midi_thru": False,
                    "audio_in": [],
                    "audio_out": ["mixer"],
                    "audio_thru": False,
                    "current_processor": 0,
                    "note_range_low": 0,
                    "note_range_high": 127,
                    "transpose": 0,
                    "midi_clone": {},
                    "slots": []
                }
            if not chains[chain_id]["audio_in"]:
                try:
                    chains[chain_id]["audio_in"] = snapshot["audio_capture"][jackname]
                except:
                    pass
            if not info:
                pass
            elif info[2] == "Audio Effect":
                chains[chain_id]["audio_processors"].append(jackname)
            elif info[2] == "MIDI Tool":
                chains[chain_id]["midi_processors"].append(jackname)
            else:
                chains[chain_id]["synth_processors"].append(jackname)
            processors[jackname] = {
                "id": proc_id,
                "type": type,
                "info": info,
                "nick": l["engine_nick"],
                "midi_chan": midi_chan,
                "bank_info": l["bank_info"],
                "preset_info": l["preset_info"],
                "controllers": l["controllers_dict"],
            }

            # Add zyngui specific stuff (should maybe be in GUI code?)
            state["zyngui"]["processors"][proc_id] = {}
            if "show_fav_presets" in l:
                state["zyngui"]["processors"][proc_id]["show_fav_presets"] = l["show_fav_presets"]
            if "active_screen_index" in l and l["active_screen_index"] >= 0:
                ["zyngui"]["processors"][proc_id]["active_screen_index"] = l["active_screen_index"]

            #TODO: Handle ZS3: "zs3_list":[128 * things]

            proc_id += 1

        note_range_state = []
        if "note_range" in snapshot:
            if len(snapshot["note_range"]) == 16:
                note_range_state = snapshot["note_range"]

        clone_state = []
        if "clone" in snapshot and len(snapshot["clone"]) == 16:
            clone_state = snapshot["clone"]

        for proc in {**snapshot["audio_routing"], **snapshot["midi_routing"]}:
            midi_chan = processors[proc]["midi_chan"]
            if isinstance(midi_chan, int):
                if midi_chan < 16:
                    chain_id = f"{midi_chan:02d}"
                    if chain_id not in chains:
                        logging.error("Can't find %s in chains", chain_id)
                    if note_range_state:
                        chains[chain_id]["note_range_low"] = note_range_state[midi_chan]["note_low"]
                        chains[chain_id]["note_range_high"] = note_range_state[midi_chan]["note_high"]
                        chains[chain_id]["transpose"] = note_range_state[midi_chan]["octave_trans"] * 12 + note_range_state[midi_chan]["halftone_trans"]
                    if clone_state:
                        chains[chain_id]["midi_clone"] = clone_state[midi_chan]

        for chain in chains.values():
            audio_out = []
            midi_out = []
            # Add audio slots
            proc_count = len(chain["audio_processors"])
            if proc_count > 0:
                slot = []
                # Populate last slot
                for proc in chain["audio_processors"]:
                    last_slot = True
                    route = snapshot["audio_routing"][proc]
                    for dst in route:
                        if dst in chain["audio_processors"]:
                            last_slot = False
                            break # processor feeds another processor so not in last slot
                    if last_slot:
                        slot.append(proc)
                        audio_out = route
                        proc_count -= 1
                if slot:
                    chain["slots"].insert(0, slot)
                while proc_count > 0:
                    slot = []
                    for proc in chain["audio_processors"]:
                        route = snapshot["audio_routing"][proc]
                        for dst in route:
                            if dst in chain["slots"][0]:
                                slot.append(proc)
                                if not audio_out:
                                    audio_out = route
                                proc_count -= 1
                                if proc_count < 1:
                                    break
                        if proc_count < 1:
                            break
                    if slot:
                        chain["slots"].insert(0, slot)

            # Add synth slot
            if chain["synth_processors"]:
                chain["slots"].insert(0, chain["synth_processors"])
                if not chain["audio_processors"]:
                    audio_out = snapshot["audio_routing"][proc]

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
                            break # processor feeds another processor so not in last slot
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
                chain["midi_thru"] = True
                chain["mixer_chan"] = None
                audio_out = []
            if not chain["midi_processors"] and not chain["synth_processors"]:
                chain["audio_thru"] = True
                chain["midi_chan"] = None
                if not audio_out:
                    audio_out = ["mixer"]
            chain["audio_out"] = audio_out
            chain["midi_out"] = midi_out

            fixed_slots = []
            for slot in chain["slots"]:
                fixed_slot = {}
                for processor in slot:
                    fixed_slot[f"{processors[processor]['id']}"] = f"{processors[processor]['nick']}"
                if fixed_slot:
                    fixed_slots.append(fixed_slot)
            chain["slots"] = fixed_slots

            chain.pop("midi_processors")
            chain.pop("synth_processors")
            chain.pop("audio_processors")

        # Fix main chain
        try:
            chains["main"] = chains.pop("256")
            chains["main"]["midi_chan"] = None
            #chains["main"]["mixer_chan"] = None
        except:
            pass

        state["chains"] = chains

        # ZS3
        try:
            state["zs3"]["zs3-0"]["mixer"] = snapshot["mixer"]
        except:
            pass

        for proc in processors.values():
            state["zs3"]["zs3-0"]["processors"][proc["id"]] = {
                "bank_info": proc["bank_info"],
                "preset_info": proc["preset_info"],
                "controllers": proc["controllers"]
            }

        return state

    def build_jackname(self, type, midi_chan):
        """Build the legacy jackname for the engine type
        
        type : Engine type
        midi_chan : Engine MIDI channel
        Returns : Jackname as string
        """

        if type == "LinuxSampler":
            if type not in self.jackname_counters:
                self.jackname_counters[type] = 0
            jackname = f"LinuxSampler:CH{self.jackname_counters[type]}_"
            self.jackname_counters[type] += 1
        elif type in ["setBfree", "Pianoteq"]:
            jackname = type
        elif type == "Audio Input":
            jackname = f"audioin-{midi_chan:02d}"
        elif type == "ZynAddSubFX":
            if type not in self.jackname_counters:
                self.jackname_counters[type] = 0
            jackname = f"zynaddsubfx:part{self.jackname_counters[type]}/"
            self.jackname_counters[type] += 1
        elif type == "FluidSynth":
            if type not in self.jackname_counters:
                self.jackname_counters[type] = 0
            jackname = f"fluidsynth:(l|r)_{self.jackname_counters[type]:02d}"
            self.jackname_counters[type] += 1
        elif type == "Aeolus":
            jackname = "aeolus"
        else:
            if type in ["Sfizz"]:
                type = type.lower()
            if type not in self.jackname_counters:
                self.jackname_counters[type] = 0
            jackname = f"{type.replace(' ', '_')}-{self.jackname_counters[type]:02d}"
            self.jackname_counters[type] += 1

        return jackname