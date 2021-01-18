#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Unit tests for zynsmf
# Tests use two letters to define order of groups and two digit integer to define order within group

import unittest
import ctypes
import jack
from time import sleep

smf = None
lib = ctypes.CDLL("/zynthian/zynthian-ui/zynlibs/zynsmf/build/libzynsmf.so")
lib.getDuration.restype = ctypes.c_double
client = jack.Client("zynsmf_unittest")

STOPPED		= 0
STARTING	= 1
PLAYING		= 2
STOPPING	= 3

class TestLibZynSmf(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        global smf
        smf = lib.addSmf()

    @classmethod
    def tearDownClass(self):
        global smf
        lib.removeSmf(smf)
        smf = None

    def test_aa00_debug(self):
       lib.enableDebug(True)
       lib.enableDebug(False)

    def test_aa01_load(self):
        self.assertTrue(lib.load(smf, bytes("./test.mid", "utf-8")))

    def test_aa02_duration(self):
        self.assertTrue(lib.load(smf, bytes("./test.mid", "utf-8")))
        self.assertEqual(lib.getDuration(smf), 6125)

    def test_aa03_position(self):
        self.assertTrue(lib.load(smf, bytes("./test.mid", "utf-8")))
        lib.setPosition(smf, 2)
        self.assertGreaterEqual(lib.getEventTime(), 2)

    def test_aa04_tracks(self):
        self.assertTrue(lib.load(smf, bytes("./test.mid", "utf-8")))
        self.assertEqual(lib.getTracks(smf), 1)

    def test_aa05_format(self):
        self.assertTrue(lib.load(smf, bytes("./test.mid", "utf-8")))
        self.assertEqual(lib.getFormat(smf), 1)

    def test_aa06_event(self):
        self.assertTrue(lib.load(smf, bytes("./test.mid", "utf-8")))
        self.assertEqual(lib.getEventTime(), 0)
        self.assertEqual(lib.getEventType(), 1)
        self.assertEqual(lib.getEventChannel(), 0)
        self.assertEqual(lib.getEventStatus(), 0x90)
        self.assertEqual(lib.getEventValue1(), 60)
        self.assertEqual(lib.getEventValue2(), 100)

    def test_ab_01_player(self):
        self.assertTrue(lib.load(smf, bytes("./test.mid", "utf-8")))
        self.assertTrue(lib.attachPlayer(smf))
        port = None
        try:
            port = client.get_port_by_name('zynmidiplayer:midi_out')
        except:
            pass
        self.assertIsNotNone(port)
        lib.removePlayer(smf)
        sleep(0.1)
        self.assertRaises(jack.JackError, client.get_port_by_name, 'zynmidiplayer:midi_out')

    def test_ab02_playback(self):
        self.assertEqual(client.transport_state, jack.STOPPED)
        self.assertTrue(lib.load(smf, bytes("./test.mid", "utf-8")))
        self.assertTrue(lib.attachPlayer(smf))
        lib.startPlayback(False)
        self.assertEqual(lib.getPlayState(), STARTING)
        client.transport_start()
        self.assertEqual(client.transport_state, jack.ROLLING)
        self.assertEqual(lib.getPlayState(), PLAYING)
        # Stop
        lib.stopPlayback(False)
        self.assertEqual(lib.getPlayState(), STOPPING)
        sleep(0.1)
        self.assertEqual(client.transport_state, jack.STOPPED)
        self.assertEqual(lib.getPlayState(), STOPPED)


unittest.main()
