from json import JSONDecoder
from zyngine import zynthian_state_manager
import logging

SNAPSHOT_FORMAT_VERSION = 1

class zynthian_legacy_snapshot:


    def __init__(self, fpath):
        """Converts legacy snapshot to current version
        
        fpath : Snapshot filename including path
        Returns : Dictionary representing zynthian state model
        """

        try:
            with open(fpath,"r") as fh:
                json = fh.read()
                snapshot = JSONDecoder().decode(json)
        except Exception as e:
            logging.error("Can't load snapshot '%s': %s" % (fpath, e))
            return None

        state = {
            'format_version': SNAPSHOT_FORMAT_VERSION,
            'active_chain': None,
            'chains': self.chain_manager.get_state(),
            'alsa_mixer': {},
            'mixer': self.zynmixer.get_state(), #TODO: Should this be in chain?
            'midi_profile_state': self.get_midi_profile_state(),
            'learned_zs3': self.learned_zs3
        }

        # Set active chain
        try:
            state['active_chain'] = f"{snapshot['index']:02d}"
        except:
            pass

        # Create chains
        found_chans = []
        found_processors = {}
        for l in snapshot["layers"]:
            if l["engine_nick"] == "MX":
                try:
                    state["alsa_mixer"]["controllers_dict"] = l["controllers_dict"]
                    state["alsa_mixer"]["current_screen_index"] = l["current_screen_index"]
                except:
                    pass
                continue
            found_processors[l["engine_jackname"]] = l
            if midi_chan in l:
                midi_chan = l["midi_chan"]
                if midi_chan in found_chans:
                    continue
                found_chans.append(midi_chan)
            else:
                midi_chan = None
            if midi_chan == 256:
                chain_id = "main"
            else:
                chain_id = f"{l['midi_chan']:02d}"
            chain_state = {}
            chain_state["midi_chan"] = midi_chan
            if ["engine_nick"] == "AI":
                chain_state["audio_through"] = True
                #TODO: Handle earlier audio only chains
            try:
                chain_state["note_range"] = snapshot["note_range"][midi_chan]
            except:
                pass
            try:
                chain_state["midi_clone"] = snapshot["midi_clone"][midi_chan]
            except:
                pass

            #TODO: Obtain from routing:
                chain_state["midi_in"] = ["MIDI IN"] # Chain MIDI input sources
                chain_state["midi_out"] = ["MIDI OUT"] # Chain MIDI output destinations
                chain_state["midi_thru"] = False # True to allow MIDI pass-through when MIDI chain empty
                chain_state["audio_in"] = ["SYSTEM"] # Chain audio input sources
                chain_state["audio_out"] = ["MIXER"] # Chain audio output destinations
                chain_state["current_processor"] = 0 # Index of the processor last selected within chain

            state[chain_id] = chain_state

        """TODO:
            Iterate through snapshot["audio_routing"] and snapshot["midi_routing"]
            Create slots
        """ 

        # Populate audio mixer
        try:
            for strip in snapshot["mixer"]:
                for param in snapshot["mixer"][strip]:
                    state["mixer"][strip][param] = snapshot["mixer"][strip][param]["value"]
        except:
            pass

        # Populate MIDI profile

        # Populate Learned ZS3
        #TODO

        # Populate multi-track audio recorder arms
        try:
            state["audio_recorder_armed"] = snapshot["audio_recorder_armed"]
        except:
            pass
        
        # Populate step sequencer
        try:
            state["zynseq_riff_b64"] = snapshot["zynseq_riff_b64"]
        except:
            pass
