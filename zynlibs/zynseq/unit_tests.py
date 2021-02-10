#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Unit tests for zynseq
# Tests use two letters to define order of groups and two digit integer to define order within group

import unittest
import ctypes
import jack
from time import sleep
import time
import filecmp
import binascii
from zynlibs.zynseq import zynseq
from zynlibs.zynseq.zynseq import libseq

client = jack.Client("riban")
midi_in = client.midi_inports.register("midi_in")
midi_out = client.midi_outports.register("midi_out")
zynseq_midi_out = None
zynseq_midi_in = None
libseq = None
last_rx = bytes(0)
send_midi = None

play_state={"STOPPED":0,"PLAYING":1,"STOPPING":2,"STARTING":3}
play_mode={"DISABLED":0,"ONESHOT": 1,"LOOP":2,"ONESHOTALL":3,"LOOPALL":4,"ONESHOTSYNC":5,"LOOPSYNC":6,"LASTPLAYMODE":6}

@client.set_process_callback
def process(frames):
    global last_rx
    global send_midi
    midi_out.clear_buffer()
    for offset, data in midi_in.incoming_midi_events():
        if data:
            last_rx = data
    midi_in.clear_buffer()
    if send_midi:
        midi_out.write_midi_event(0, send_midi)
        send_midi = None

client.activate()

class TestLibZynSeq(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        global libseq
        global zynseq_midi_out
        global zynseq_midi_in
        libseq = ctypes.CDLL("/zynthian/zynthian-ui/zynlibs/zynseq/build/libzynseq.so")
        libseq.init(True)
        zynseq_midi_out = client.get_port_by_name('zynthstep:output')
        zynseq_midi_in = client.get_port_by_name('zynthstep:input')
        midi_in.connect(zynseq_midi_out)
        midi_out.connect(zynseq_midi_in)
    #
    def test_aa00_debug(self):
       libseq.enableDebug(True)
       libseq.enableDebug(False)
    def test_aa01_loadfile(self):
        self.assertTrue(libseq.load(bytes("/zynthian/zynthian-my-data/zynseq/default.zynseq", "utf-8")))
    #
    def test_aa02_savefile(self):
        libseq.save(bytes("/tmp/test.zynseq", "utf-8"))
        self.assertTrue(filecmp.cmp("/zynthian/zynthian-my-data/zynseq/default.zynseq", "/tmp/test.zynseq"))
    # Check currently selected pattern has defined beat type, steps per beat [1|2|3|4|6|8|12|24] and quantity of beats in pattern
    def check_pattern(self, beat_type, steps_per_beat, beats_in_pattern):
        steps_in_pattern = beats_in_pattern * steps_per_beat
        clocks_per_step = 24 / steps_per_beat
        self.assertEqual(libseq.getSteps(), steps_in_pattern)
        self.assertEqual(libseq.getBeatType(), beat_type)
        self.assertEqual(libseq.getStepsPerBeat(), steps_per_beat)
        self.assertEqual(libseq.getBeatsInPattern(), beats_in_pattern)
        self.assertEqual(libseq.getClocksPerStep(), clocks_per_step)
        self.assertEqual(libseq.getPatternLength(libseq.getPatternIndex()), clocks_per_step * steps_in_pattern)
    # Pattern tests
    def test_ac00_select_pattern(self):
        libseq.selectPattern(999)
        self.assertEqual(libseq.getPatternIndex(), 999)
        self.check_pattern(4, 4, 4)
    #
    def test_ac01_set_beats(self):
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(5)
        self.check_pattern(4, 4, 5)
    #
    def test_ac02_set_steps_per_beat(self):
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(5)
        self.assertFalse(libseq.setStepsPerBeat(7)) # Not a permitted value
        self.check_pattern(4, 4, 5)
        self.assertTrue(libseq.setStepsPerBeat(8))
        self.check_pattern(4, 8, 5)
    #
    def test_ac03_add_note(self):
        libseq.selectPattern(999)
        self.assertTrue(libseq.addNote(0,60,100,4))
        self.assertEqual(libseq.getNoteVelocity(0,60), 100)
        self.assertEqual(libseq.getNoteDuration(0,60), 4)
    #
    def test_ac04_add_note_too_long(self):
        libseq.selectPattern(999)
        self.assertTrue(libseq.addNote(0,60,100,4))
        self.assertFalse(libseq.addNote(0,60,100,200))
        self.assertEqual(libseq.getNoteVelocity(0,60), 100)
        self.assertEqual(libseq.getNoteDuration(0,60), 4)
    #
    def test_ac05_set_note_velocity(self):
        libseq.selectPattern(999)
        self.assertTrue(libseq.addNote(0,60,100,4))
        libseq.setNoteVelocity(0,60,123)
        self.assertEqual(libseq.getNoteVelocity(0,60), 123)
    #
    def test_ac06_set_note_duration(self):
        libseq.selectPattern(999)
        libseq.addNote(0,60,123,2)
        self.assertEqual(libseq.getNoteDuration(0,60), 2)
    #
    def test_ac07_transpose(self):
        libseq.selectPattern(999)
        libseq.addNote(0,60,123,2)
        libseq.transpose(5)
        self.assertEqual(libseq.getNoteDuration(0,65), 2)
        self.assertEqual(libseq.getNoteVelocity(0,65), 123)
    #
    def test_ac08_copy_pattern(self):
        libseq.selectPattern(999)
        libseq.addNote(0,60,123,2)
        libseq.copyPattern(999, 998)
        libseq.selectPattern(998)
        self.assertEqual(libseq.getNoteDuration(0,60), 2)
        self.assertEqual(libseq.getNoteVelocity(0,60), 123)
    #
    def test_ac09_clear_pattern(self):
        libseq.clear()
        self.assertEqual(libseq.getNoteDuration(0,65), 0)
    #
    def test_ac10_is_pattern_modified(self):
        libseq.selectPattern(999)
        libseq.addNote(0,60,100,4)
        self.assertTrue(libseq.isPatternModified())
        self.assertFalse(libseq.isPatternModified())

    # Trigger tests
    def test_ad00_trigger_channel(self):
        self.assertEqual(libseq.getTriggerChannel(), 0xFF)
        libseq.setTriggerChannel(5)
        self.assertEqual(libseq.getTriggerChannel(), 5)
        libseq.setTriggerChannel(16)
        self.assertEqual(libseq.getTriggerChannel(), 0xFF)
        self.assertEqual(libseq.getTriggerNote(0,0), 0xFF)
        libseq.setTriggerNote(0,0,0)
        self.assertEqual(libseq.getTriggerNote(0,0), 0)
        libseq.setTriggerNote(0,0,127)
        self.assertEqual(libseq.getTriggerNote(0,0), 127)
        libseq.setTriggerNote(0,0,128)
        self.assertEqual(libseq.getTriggerNote(0,0), 0xFF)

    # Track tests
    def test_ae00_track(self):
        self.assertEqual(libseq.getTracks(0,0), 1)
        self.assertTrue(libseq.addPattern(0,0,0,0,5,False))
        self.assertEqual(libseq.getPattern(0,0,0,0), 5)
        libseq.removePattern(0,0,0,0)
        self.assertEqual(libseq.getPattern(0,0,0,0), -1)

    # Sequence tests
    def test_af00_sequence_channel(self):
        self.assertEqual(libseq.getChannel(0,0,0), 0xFF)
        libseq.setChannel(0,0,0,0)
        self.assertEqual(libseq.getChannel(0,0,0), 0)
        libseq.setChannel(0,0,0,15)
        self.assertEqual(libseq.getChannel(0,0,0), 15)
        libseq.setChannel(0,0,0,16)
        self.assertEqual(libseq.getChannel(0,0,0), 0xFF)
    #
    def test_af01_sequence_mode(self):
        self.assertEqual(libseq.getPlayMode(0,0), play_mode["LOOPALL"])
        libseq.setPlayMode(0,0,play_mode["LOOPSYNC"])
        self.assertEqual(libseq.getPlayMode(0,0), play_mode["LOOPSYNC"])


'''
    # Sequence tests
    def test_ae00_add_pattern(self):
        sequence = libseq.getSequence(1,1)
        self.assertTrue(libseq.addPattern(sequence,4,998,False))
        self.assertEqual(libseq.getPattern(sequence, 4), 998)
        self.assertFalse(libseq.addPattern(sequence,0,998,False))
        self.assertEqual(libseq.getPattern(sequence, 0), -1)
        self.assertEqual(libseq.getPattern(sequence, 4), 998)
        self.assertTrue(libseq.addPattern(sequence,0,998,True))
        self.assertEqual(libseq.getPattern(sequence, 0), 998)
        self.assertEqual(libseq.getPattern(sequence, 4), -1)
    #
    def test_ae01_remove_pattern(self):
        sequence = libseq.getSequence(1,1)
        libseq.removePattern(sequence, 0)
        self.assertEqual(libseq.getPattern(sequence, 0), -1)
    # Impact on other elements of changing patterns
    def test_af00_change_pattern_length(self):
        sequence = libseq.getSequence(1,1)
        libseq.clearSong(1)
        self.assertEqual(libseq.getSequenceLength(sequence), 0)
        libseq.selectPattern(1)
        libseq.clear()
        libseq.setBeatsInPattern(4)
        libseq.setStepsPerBeat(4)
        libseq.addPattern(sequence,0,1,True)
        self.assertEqual(libseq.getSequenceLength(sequence), 24*4)
        libseq.setBeatsInPattern(6)
        self.assertEqual(libseq.getSequenceLength(sequence), 24*6)
        libseq.setStepsPerBeat(8)
        self.assertEqual(libseq.getSequenceLength(sequence), 24*6)
    # Playback mode tests
    def test_ag00_sequence_playstate(self):
        self.assertEqual(client.transport_state, jack.STOPPED) # Transport should be stopped during init
        sequence = libseq.getSequence(1001,libseq.addTrack(1001))
        beats = 4
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(beats)
        libseq.addPattern(sequence,0,999,True)
        self.assertEqual(libseq.getSequenceLength(sequence), beats * 24)
        libseq.setPlayMode(sequence, play_mode["LOOPSYNC"])
        # Start playback - transport is not rolling so should start immediately from start of current bar
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        tb=client.transport_query()
        self.assertEqual(tb[0], jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for beat in range(0,5):
            print("Beat", beat % 4 + 1)
            self.assertEqual(tb[1]['bar'], 1)
            self.assertEqual(tb[1]['beat'], beat % 4 + 1)
            sleep(0.5)
            tb=client.transport_query()
        # Stop playback - loop sync should should continue playing until loop point
        libseq.setPlayState(sequence, play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPING"])
        sleep(2)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        self.assertEqual(client.transport_state, jack.STOPPED) # Transport stops when last sequence stops
        # Toggle playback to start
        libseq.togglePlayState(sequence)
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        self.assertEqual(client.transport_query()[1]['beat'], 1)
        sleep(1)
        # Toggle playback to stop
        libseq.togglePlayState(sequence)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPING"])
        sleep(1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
    # Check sequence starts at sync point
    def test_ag01_sync_play(self):
        self.assertEqual(client.transport_state, jack.STOPPED)
        sequence1 = libseq.getSequence(1001,libseq.addTrack(10001))
        sequence2 = libseq.getSequence(1001,libseq.addTrack(10001))
        libseq.addPattern(sequence1,0,999,True)
        libseq.addPattern(sequence2,0,999,True)
        libseq.setPlayMode(sequence1,play_mode["LOOPSYNC"]) 
        libseq.setPlayMode(sequence2,play_mode["LOOPSYNC"]) 
        libseq.setPlayState(sequence1, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence1), play_state["PLAYING"])
        libseq.setPlayState(sequence2, play_state["STARTING"])
        sleep(1.8)
        self.assertEqual(libseq.getPlayState(sequence2), play_state["STARTING"])
        sleep(0.5)
        self.assertEqual(libseq.getPlayState(sequence2), play_state["PLAYING"])
        libseq.setPlayState(sequence1, play_state["STOPPING"])
        libseq.setPlayState(sequence2, play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequence1), play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequence2), play_state["STOPPING"])
        sleep(2)
        self.assertEqual(libseq.getPlayState(sequence1), play_state["STOPPED"])
        self.assertEqual(libseq.getPlayState(sequence2), play_state["STOPPED"])
    # Check different playback modes assuming tempo=120bpm (2 beats per second, 4 beats per bar (sync / loop point))
    def test_ag02_playback_modes(self):
        self.assertEqual(client.transport_state, jack.STOPPED)
        sequence = libseq.getSequence(1001,libseq.addTrack(1001))
        libseq.clearSequence(sequence)
        beats = 5
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(beats)
        libseq.addPattern(sequence,0,999,True)
        self.assertEqual(libseq.getSequenceLength(sequence), beats * 24)
        mode = play_mode["DISABLED"]
        libseq.setPlayMode(sequence, mode)
        self.assertEqual(libseq.getPlayMode(sequence), mode)
        libseq.setPlayState(sequence, play_state["STARTING"])
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        self.assertEqual(client.transport_state, jack.STOPPED)
        # Test firing one-shot and leaving to complete
        mode = play_mode["ONESHOT"]
        libseq.setPlayMode(sequence, mode)
        self.assertEqual(libseq.getPlayMode(sequence), mode)
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        sleep(2.2)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        sleep(0.3)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        # Test one-shot and stop before end
        for wait in range(0, 8):
            # fire on beat 2 and wait until beat 1 for start
            if client.transport_query()[1]['beat'] == 2:
                break
            sleep(0.25)
        self.assertEqual(client.transport_query()[1]['beat'], 2)
        libseq.setPlayState(sequence, play_state["STARTING"])
        self.assertEqual(libseq.getPlayState(sequence), play_state["STARTING"])
        for wait in range(0, 8):
            if client.transport_query()[1]['beat'] == 1:
                break
            self.assertEqual(libseq.getPlayState(sequence), play_state["STARTING"])
            sleep(0.25)
        self.assertEqual(client.transport_query()[1]['beat'], 1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        libseq.setPlayState(sequence, play_state["STOPPING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        sleep(2) #TODO: This delay waits for end of bar but we may change library to stop transport earlier
        self.assertEqual(client.transport_state, jack.STOPPED)
        # Test loop
        mode = play_mode["LOOP"]
        libseq.setPlayMode(sequence, mode)
        self.assertEqual(libseq.getPlayMode(sequence), mode)
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        sleep(1.8)
        tb=client.transport_query()
        self.assertEqual(tb[1]['beat'], 4)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        sleep(0.2)
        tb=client.transport_query()
        self.assertEqual(tb[1]['beat'], 1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        libseq.setPlayState(sequence, play_state["STOPPING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        sleep(2) #TODO: This delay waits for end of bar but we may change library to stop transport earlier
        self.assertEqual(client.transport_state, jack.STOPPED)
        # Test one-shot-all
        mode = play_mode["ONESHOTALL"]
        libseq.setPlayMode(sequence, mode)
        self.assertEqual(libseq.getPlayMode(sequence), mode)
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for beat in range (0,5):
            self.assertEqual(client.transport_query()[1]['beat'], (beat%4)+1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
            sleep(0.5)
        self.assertEqual(client.transport_query()[1]['beat'], 2)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        sleep(2) #TODO: This delay waits for end of bar but we may change library to stop transport earlier
        self.assertEqual(client.transport_state, jack.STOPPED)
        # one-shot-all, stopping before end
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        libseq.setPlayState(sequence, play_state["STOPPING"])
        for beat in range (0,5):
            self.assertEqual(client.transport_query()[1]['beat'], (beat%4)+1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPING"])
            sleep(0.5)
        self.assertEqual(client.transport_query()[1]['beat'], 2)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        sleep(2) #TODO: This delay waits for end of bar but we may change library to stop transport earlier
        self.assertEqual(client.transport_state, jack.STOPPED)
        # loop all
        mode = play_mode["LOOPALL"]
        libseq.setPlayMode(sequence, mode)
        self.assertEqual(libseq.getPlayMode(sequence), mode)
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for beat in range (0,5):
            self.assertEqual(client.transport_query()[1]['beat'], (beat%4)+1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
            sleep(0.5)
        libseq.setPlayState(sequence, play_state["STOPPING"])
        for beat in range (1,6):
            self.assertEqual(client.transport_query()[1]['beat'], (beat%4)+1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPING"])
            sleep(0.5)
        self.assertEqual(client.transport_query()[1]['beat'], 3)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        sleep(2) #TODO: This delay waits for end of bar but we may change library to stop transport earlier
        self.assertEqual(client.transport_state, jack.STOPPED)
        # One shot sync
        mode = play_mode["ONESHOTSYNC"]
        libseq.setPlayMode(sequence, mode)
        self.assertEqual(libseq.getPlayMode(sequence), mode)
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for beat in range (0,5):
            self.assertEqual(client.transport_query()[1]['beat'], (beat%4)+1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
            sleep(0.5)
        self.assertEqual(client.transport_query()[1]['beat'], 2)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        sleep(2) #TODO: This delay waits for end of bar but we may change library to stop transport earlier
        self.assertEqual(client.transport_state, jack.STOPPED)
        # One shot sync - stop before end
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        libseq.setPlayState(sequence, play_state["STOPPING"])
        for beat in range (0,4):
            self.assertEqual(client.transport_query()[1]['beat'], (beat%4)+1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPING"])
            sleep(0.5)
        self.assertEqual(client.transport_query()[1]['beat'], 1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        self.assertEqual(client.transport_state, jack.STOPPED)
        # loop sync
        mode = play_mode["LOOPSYNC"]
        libseq.setPlayMode(sequence, mode)
        self.assertEqual(libseq.getPlayMode(sequence), mode)
        libseq.setPlayState(sequence, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.transportGetPlayStatus(), jack.ROLLING)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for beat in range (0,5):
            self.assertEqual(client.transport_query()[1]['beat'], (beat%4)+1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
            sleep(0.5)
        libseq.setPlayState(sequence, play_state["STOPPING"])
        for beat in range (1,4):
            self.assertEqual(client.transport_query()[1]['beat'], (beat%4)+1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPING"])
            sleep(0.5)
        self.assertEqual(client.transport_query()[1]['beat'], 1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        self.assertEqual(client.transport_state, jack.STOPPED)
    # Playback tests
    def test_ah00_routing(self):
        self.assertEqual(midi_in.connections, [zynseq_midi_out])
        self.assertEqual(midi_out.connections, [zynseq_midi_in])
    # Play individual note live
    def test_ah01_play_notes(self):
        for velocity in range(100, 20, -20):
            for note in (60, 64, 67, 72):
                libseq.playNote(note, velocity, 0, 200)
                sleep(0.1) #TODO: This should be 0.01 delay but is failing - check Python minimum delay - seems to be fairly linear at 10ms so check out zynseq code
                self.assertEqual(binascii.hexlify(last_rx).decode(), "90%02x%02x"%(note,velocity)) # Note on
                sleep(0.2)
                self.assertEqual(binascii.hexlify(last_rx).decode(), "90%02x00"%(note)) # Note off
                sleep(0.1)
        libseq.playNote(0x40,0x50,1,400)
        sleep(0.01)
        self.assertEqual(binascii.hexlify(last_rx).decode(), "914050") # Note on
        sleep(0.2)
        self.assertEqual(binascii.hexlify(last_rx).decode(), "914050") # Note sustaining
        sleep(0.2)
        self.assertEqual(binascii.hexlify(last_rx).decode(), "914000") # Note off
        libseq.playNote(0x60,0x70,16,200) # Out of bounds MIDI channel
        sleep(0.1)
        self.assertEqual(binascii.hexlify(last_rx).decode(), "914000") # same as previous because this fails to sound
    # Playback sequence
    def test_ah02_playback(self):
        sleep(0.1)
        self.assertEqual(client.transport_state, jack.STOPPED)
        sequence = libseq.getSequence(1001,libseq.addTrack(1001))
        libseq.clearSequence(sequence)
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(4)
        libseq.setStepsPerBeat(4)
        libseq.clear()
        libseq.addNote(0, 0x40, 101, 1)
        libseq.addNote(4, 0x41, 102, 1)
        libseq.addNote(8, 0x42, 103, 1)
        libseq.addNote(12, 0x43, 104, 1)
        libseq.addPattern(sequence,0,999,True)
        libseq.setPlayMode(sequence, play_mode["ONESHOT"])
        step_duration = (60 / 120) / 4
        libseq.setPlayState(sequence, play_state["STARTING"])
        for i in range(0,4):
            sleep(step_duration * 0.5)
            self.assertEqual(binascii.hexlify(last_rx).decode(), "90%02x%02x"%(0x40+i,101+i)) # Note on
            sleep(step_duration * 1)
            self.assertEqual(binascii.hexlify(last_rx).decode(), "90%02x00"%(0x40+i)) # Note off
            sleep(step_duration * 2.5)
            self.assertEqual(binascii.hexlify(last_rx).decode(), "90%02x00"%(0x40+i)) # Note off
        sleep(2)
    # MIDI playback channel
    def test_ah03_playback_channel(self):
        self.assertEqual(client.transport_state, jack.STOPPED)
        libseq.selectSong(2)
        sequence = libseq.getSequence(1002,libseq.addTrack(1002))
        libseq.addPattern(sequence,0,100,True)
        libseq.setPlayMode(sequence, play_mode["ONESHOT"])
        libseq.selectPattern(100)
        libseq.setBeatsInPattern(1)
        libseq.setStepsPerBeat(4)
        libseq.addNote(0, 60, 100, 4)
        for channel in range(0, 16, 4): #TODO: Test out of bounds channels <0, >15
            libseq.setChannel(sequence, channel)
            libseq.setPlayState(sequence, play_state["STARTING"])
            sleep(0.1)
            self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
            self.assertEqual(binascii.hexlify(last_rx).decode(), "9%x3c64"%(channel)) # Note on
            sleep(2) #TODO: Set bar length shorter to allow quicker iteration
            self.assertEqual(client.transport_state, jack.STOPPED)
    # MIDI trigger inputs
    def test_ah04_trigger(self):
        global send_midi
        libseq.selectSong(1)
        sequence = libseq.getSequence(1001,libseq.addTrack(1001))
        libseq.clearSequence(sequence) #TODO: Do we need to clear sequence - should check it is clear by default
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(4)
        libseq.setStepsPerBeat(4)
        libseq.clear()
        libseq.addNote(0, 60, 101, 1)
        libseq.addNote(4, 61, 102, 1)
        libseq.addNote(8, 62, 103, 1)
        libseq.addNote(12, 63, 104, 1)
        libseq.addPattern(sequence,0,999,True)
        libseq.setPlayMode(sequence, play_mode["ONESHOTSYNC"])
        libseq.setTriggerChannel(5)
        self.assertEqual(libseq.getTriggerChannel(), 5)
        libseq.setTriggerNote(sequence, 40)
        self.assertEqual(libseq.getTriggerNote(sequence), 40)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        send_midi = (0x90, 40, 127) # Wrong MIDI channel - should not trigger
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        send_midi = (0x95, 41, 127) # Wrong MIDI note - should not trigger
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        send_midi = (0x95, 40, 127) # This should trigger
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        send_midi = (0x95, 40, 0) # Note off should not affect
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        send_midi = (0x95, 40, 100) # This should trigger stop
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPING"])
        send_midi = (0x95, 40, 0) # Note off should not affect
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPING"])
        sleep(2)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
    # Sequence play tallies
    def test_ah05_tallies(self):
        client.transport_stop()
        sleep(0.3)
        global last_rx
        last_rx = bytes(0)
        sequence1 = libseq.getSequence(1001,libseq.addTrack(1001))
        sequence2 = libseq.getSequence(1001,libseq.addTrack(1001))
        self.assertEqual(libseq.getTallyChannel(sequence1), 255) # New sequences should have tally disabled
        libseq.setTallyChannel(sequence1, 4)
        self.assertEqual(libseq.getTallyChannel(sequence1), 4)
        libseq.setTriggerNote(sequence1, 0x10)
        libseq.selectPattern(2)
        libseq.clear()
        libseq.setBeatsInPattern(2)
        libseq.addPattern(sequence1, 999, 0, True)
        libseq.addPattern(sequence2, 999, 0, True)
        libseq.setPlayMode(sequence1, play_mode["LOOPSYNC"])
        libseq.setPlayMode(sequence2, play_mode["LOOPSYNC"])
        libseq.setPlayState(sequence2, play_state["STARTING"]) # Start a loop playing so that we can watch sequence1 state progress
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence2), play_state["PLAYING"])
        libseq.setPlayState(sequence1, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence1), play_state["STARTING"])
        self.assertEqual(binascii.hexlify(last_rx).decode(), "941005") # Starting tally = 5
        sleep(2)
        self.assertEqual(libseq.getPlayState(sequence1), play_state["PLAYING"])
        self.assertEqual(binascii.hexlify(last_rx).decode(), "941001") # Playing tally = 1
        libseq.setPlayState(sequence1, play_state["STOPPING"])
        libseq.setPlayState(sequence2, play_state["STOPPING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequence1), play_state["STOPPING"])
        self.assertEqual(binascii.hexlify(last_rx).decode(), "941004") # Stopping tally = 4
        sleep(2)
        self.assertEqual(binascii.hexlify(last_rx).decode(), "941003") # Stopped tally = 3
        self.assertEqual(libseq.getPlayState(sequence1), play_state["STOPPED"])
        self.assertEqual(libseq.getPlayState(sequence2), play_state["STOPPED"])
    # Exclusive groups
    def test_ah06_groups(self):
        client.transport_stop()
        sleep(0.3)
        libseq.selectSong(2)
        libseq.selectPattern(1)
        libseq.clear()
        libseq.setBeatsInPattern(4)
        libseq.setStepsPerBeat(4)
        sequenceA1 = libseq.getSequence(1002,libseq.addTrack(1002))
        sequenceA2 = libseq.getSequence(1002,libseq.addTrack(1002))
        sequenceB1 = libseq.getSequence(1002,libseq.addTrack(1002))
        libseq.addPattern(sequenceA1, 0, 1, True)
        libseq.addPattern(sequenceA2, 0, 1, True)
        libseq.addPattern(sequenceB1, 0, 1, True)
        libseq.setGroup(sequenceA1,1)
        libseq.setGroup(sequenceA2,1)
        libseq.setGroup(sequenceB1,2)
        libseq.setPlayMode(sequenceA1, play_mode["LOOPSYNC"])
        libseq.setPlayMode(sequenceA2, play_mode["LOOPSYNC"])
        libseq.setPlayMode(sequenceB1, play_mode["LOOPSYNC"])
        libseq.setPlayState(sequenceA1, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequenceA1), play_state["PLAYING"])
        self.assertEqual(libseq.getPlayState(sequenceA2), play_state["STOPPED"])
        self.assertEqual(libseq.getPlayState(sequenceB1), play_state["STOPPED"])
        libseq.setPlayState(sequenceA2, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequenceA1), play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequenceA2), play_state["STARTING"])
        self.assertEqual(libseq.getPlayState(sequenceB1), play_state["STOPPED"])
        libseq.setPlayState(sequenceB1, play_state["STARTING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequenceA1), play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequenceA2), play_state["STARTING"])
        self.assertEqual(libseq.getPlayState(sequenceB1), play_state["STARTING"])
        libseq.setPlayState(sequenceA2, play_state["STOPPING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequenceA1), play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequenceA2), play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequenceB1), play_state["STARTING"])
        libseq.setPlayState(sequenceB1, play_state["STOPPING"])
        sleep(0.1)
        self.assertEqual(libseq.getPlayState(sequenceA1), play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequenceA2), play_state["STOPPING"])
        self.assertEqual(libseq.getPlayState(sequenceB1), play_state["STOPPING"])
        sleep(2)
        self.assertEqual(libseq.getPlayState(sequenceA1), play_state["STOPPED"])
        self.assertEqual(libseq.getPlayState(sequenceA2), play_state["STOPPED"])
        self.assertEqual(libseq.getPlayState(sequenceB1), play_state["STOPPED"])
    # Song management
    def test_ai00_song(self):
        client.transport_stop()
        libseq.selectSong(5)
        self.assertEqual(libseq.getSong(), 5)
        libseq.clearSong(5)
        self.assertEqual(libseq.getTracks(5), 0)
        self.assertEqual(libseq.addTrack(5), 0)
        self.assertEqual(libseq.addTrack(5), 1)
        self.assertEqual(libseq.getTracks(5), 2)
        libseq.removeTrack(5,0)
        self.assertEqual(libseq.getTracks(5), 1)
        self.assertNotEqual(libseq.getSequence(5,0), 0)
        libseq.clearSong(6)
        self.assertEqual(libseq.getTracks(6), 0)
        libseq.copySong(5, 6)
        self.assertEqual(libseq.getTracks(6), 1)
        #TODO: Check content of copied song
    def test_ai01_timesig(self):
        libseq.selectSong(5)
        self.assertEqual(libseq.getTimeSigAt(5, 0), 0x0404) # Default time signature should be 4/4
        sleep(0.1)
        self.assertEqual(client.transport_state, jack.STOPPED)
        sequence = libseq.getSequence(1005,libseq.addTrack(1005))
        libseq.clearSequence(sequence)
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(4)
        libseq.setStepsPerBeat(4)
        libseq.clear()
        libseq.addNote(0, 0x41, 0x64, 1)
        libseq.addNote(4, 0x42, 0x64, 1)
        libseq.addNote(8, 0x43, 0x64, 1)
        libseq.addNote(12, 0x44, 0x64, 1)
        libseq.addPattern(sequence,0,999,True)
        libseq.setPlayMode(sequence, play_mode["LOOPSYNC"])
        step_duration = (60 / 120) / 4
        libseq.setPlayState(sequence, play_state["STARTING"])
        for i in range(0,100):
            sleep(0.001)
            if libseq.getPlayState(sequence) == play_state["PLAYING"]:
                break
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for i in range(0,4):
            sleep(step_duration)
            if binascii.hexlify(last_rx).decode() == "904100":
                break
        self.assertEqual(binascii.hexlify(last_rx).decode(), "904100")
        for i in range(0,4):
            sleep(step_duration)
            if binascii.hexlify(last_rx).decode() == "904200":
                break
        self.assertEqual(binascii.hexlify(last_rx).decode(), "904200")
        for i in range(0,4):
            sleep(step_duration)
            if binascii.hexlify(last_rx).decode() == "904300":
                break
        self.assertEqual(binascii.hexlify(last_rx).decode(), "904300")
        for i in range(0,4):
            sleep(step_duration)
            if binascii.hexlify(last_rx).decode() == "904400":
                break
        self.assertEqual(binascii.hexlify(last_rx).decode(), "904400")
        libseq.setPlayState(sequence, play_state["STOPPING"])
        sleep(2)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        self.assertEqual(client.transport_state, jack.STOPPED)
        libseq.addTimeSigEvent(5, 2, 4, 0)
        self.assertEqual(libseq.getTimeSigAt(5, 1, 0), 0x0204)
        self.assertEqual(libseq.getTimeSigAt(5, 4, 0), 0x0204)
        libseq.setPlayState(sequence, play_state["STARTING"])
        for i in range(0,100):
            sleep(0.001)
            if libseq.getPlayState(sequence) == play_state["PLAYING"]:
                break
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for i in range(0,4):
            sleep(step_duration)
            if binascii.hexlify(last_rx).decode() == "904100":
                break
        self.assertEqual(binascii.hexlify(last_rx).decode(), "904100")
        for i in range(0,4):
            sleep(step_duration)
            if binascii.hexlify(last_rx).decode() == "904200":
                break
        self.assertEqual(binascii.hexlify(last_rx).decode(), "904200")
        for i in range(0,4):
            sleep(step_duration)
            if binascii.hexlify(last_rx).decode() == "904100":
                break
        self.assertEqual(binascii.hexlify(last_rx).decode(), "904100")
        for i in range(0,4):
            sleep(step_duration)
            if binascii.hexlify(last_rx).decode() == "904200":
                break
        self.assertEqual(binascii.hexlify(last_rx).decode(), "904200")
        libseq.setPlayState(sequence, play_state["STOPPING"])
        sleep(2)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        self.assertEqual(client.transport_state, jack.STOPPED)
    def test_ai02_tempo(self):
        client.transport_stop()
        sleep(0.1)
        self.assertEqual(client.transport_state, jack.STOPPED)
        libseq.selectSong(5)
        self.assertEqual(libseq.getTempoAt(5, 1, 0), 120) # Default tempo should be 120
        sequence = libseq.getSequence(1005,libseq.addTrack(1005))
        libseq.clearSequence(sequence)
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(4)
        libseq.setStepsPerBeat(4)
        libseq.clear()
        libseq.addNote(0, 0x41, 0x64, 1)
        libseq.addNote(4, 0x42, 0x64, 1)
        libseq.addNote(8, 0x43, 0x64, 1)
        libseq.addNote(12, 0x44, 0x64, 1)
        libseq.addPattern(sequence,0,999,True)
        libseq.setPlayMode(sequence, play_mode["ONESHOTSYNC"])
        step_duration = (60 / 120) / 4
        libseq.addTimeSigEvent(5, 4, 4, 0)
        libseq.setPlayState(sequence, play_state["STARTING"])
        for i in range(0,100):
            sleep(0.001)
            if libseq.getPlayState(sequence) == play_state["PLAYING"]:
                break
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for i in range(0,300):
            sleep(0.01)
            if libseq.getPlayState(sequence) == play_state["STOPPED"]:
                break
        self.assertEqual(int((i / 100 + step_duration / 2) / step_duration), 16)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        for i in range(0,400):
            sleep(0.01)
            if client.transport_state ==jack.STOPPED:
                break
        self.assertEqual(client.transport_state, jack.STOPPED)
        # Change tempo
        libseq.addTempo(5, 60, 1, 0) # Halve the tempo
        step_duration = (60 / 60) / 4
        libseq.setPlayState(sequence, play_state["STARTING"])
        for i in range(0,100):
            sleep(0.001)
            if libseq.getPlayState(sequence) == play_state["PLAYING"]:
                break
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for i in range(0,600):
            sleep(0.01)
            if libseq.getPlayState(sequence) == play_state["STOPPED"]:
                break
        self.assertEqual(int((i / 100 + step_duration / 2) / step_duration), 16)
        self.assertEqual(libseq.getPlayState(sequence), play_state["STOPPED"])
        for i in range(0,400):
            sleep(0.01)
            if client.transport_state ==jack.STOPPED:
                break
        self.assertEqual(client.transport_state, jack.STOPPED)
    def test_ai02_tempo(self):
        global last_rx
        libseq.enableDebug()
        libseq.selectSong(1)
        sleep(0.1)
        self.assertEqual(client.transport_state, jack.STOPPED)
        sequence = libseq.getSequence(1001,libseq.addTrack(1001))
        libseq.clearSequence(sequence)
        libseq.selectPattern(999)
        libseq.setBeatsInPattern(1)
        libseq.setStepsPerBeat(4)
        libseq.clear()
        libseq.addNote(0, 0x41, 0x64, 1)
        libseq.addPattern(sequence,0,999,True)
        libseq.setPlayMode(sequence, play_mode["LOOPSYNC"])
        libseq.addTimeSigEvent(1, 1, 4, 1)
        libseq.setPlayState(sequence, play_state["STARTING"])
        for i in range(0,100):
            sleep(0.001)
            if libseq.getPlayState(sequence) == play_state["PLAYING"]:
                break
        self.assertEqual(libseq.getPlayState(sequence), play_state["PLAYING"])
        for tempo in range(120, 20, -40):
            libseq.setTempo(tempo)
            time1 = time.time()
            last_rx = bytes(0)
            while (binascii.hexlify(last_rx).decode() != "904100") and (time.time() < time1 + 1):
                pass
            time1 = time.time()
            last_rx = bytes(0)
            while (binascii.hexlify(last_rx).decode() != "904100") and (time.time() < time1 + 1):
                pass
            time2 = time.time()
            min_time = 58/tempo
            max_time = 62/tempo
            self.assertTrue(min_time < time2-time1 < max_time)
'''

    #TOOO Check beat type, sendMidiXXX (or remove), isSongPlaying, getTriggerChannel, setTriggerChannel, getTriggerNote, setTriggerNote, setInputChannel, getInputChannel, setScale, getScale, setTonic, getTonic, setChannel, getChannel, setOutput, setTempo, getTempo, setSongPosition, getSongPosition, startSong, pauseSong, toggleSong, solo, transportXXX

unittest.main()
