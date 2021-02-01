#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Unit tests for zynsmf
# Tests use two letters to define order of groups and two digit integer to define order within group

import unittest
import jack
from time import sleep

from zynlibs.zynsmf import zynsmf
from zynlibs.zynsmf.zynsmf import libsmf

smf = None
client = jack.Client("zynsmf_unittest")

STOPPED		= 0
STARTING	= 1
PLAYING		= 2
STOPPING	= 3

class TestLibZynSmf(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        global smf
        smf = libsmf.addSmf()

    @classmethod
    def tearDownClass(self):
        global smf
        libsmf.removeSmf(smf)
        smf = None

    def test_aa00_debug(self):
       libsmf.enableDebug(True)
       libsmf.enableDebug(False)

    def test_aa01_load(self):
        self.assertTrue(zynsmf.load(smf, "./test.mid"))

    def test_aa02_duration(self):
        self.assertTrue(zynsmf.load(smf, "./test.mid"))
        self.assertEqual(libsmf.getDuration(smf), 6125)

    def test_aa03_position(self):
        self.assertTrue(zynsmf.load(smf, "./test.mid"))
        libsmf.setPosition(smf, 2)
        self.assertGreaterEqual(libsmf.getEventTime(), 2)

    def test_aa04_tracks(self):
        self.assertTrue(zynsmf.load(smf, "./test.mid"))
        self.assertEqual(libsmf.getTracks(smf), 1)

    def test_aa05_format(self):
        self.assertTrue(zynsmf.load(smf, "./test.mid"))
        self.assertEqual(libsmf.getFormat(smf), 1)

    def test_aa06_event(self):
        self.assertTrue(zynsmf.load(smf, "./test.mid"))
        self.assertEqual(libsmf.getEventTime(), 0)
        self.assertEqual(libsmf.getEventType(), 1)
        self.assertEqual(libsmf.getEventChannel(), 0)
        self.assertEqual(libsmf.getEventStatus(), 0x90)
        self.assertEqual(libsmf.getEventValue1(), 60)
        self.assertEqual(libsmf.getEventValue2(), 100)

    def test_ab_01_player(self):
        self.assertTrue(zynsmf.load(smf, "./test.mid"))
        self.assertTrue(libsmf.attachPlayer(smf))
        port = None
        try:
            port = client.get_port_by_name('zynmidiplayer:midi_out')
        except:
            pass
        self.assertIsNotNone(port)
        libsmf.removePlayer(smf)
        sleep(0.1)
        self.assertRaises(jack.JackError, client.get_port_by_name, 'zynmidiplayer:midi_out')

    def test_ab02_playback(self):
        self.assertEqual(client.transport_state, jack.STOPPED)
        self.assertTrue(zynsmf.load(smf, "./test.mid"))
        self.assertTrue(libsmf.attachPlayer(smf))
        libsmf.startPlayback(False)
        self.assertEqual(libsmf.getPlayState(), STARTING)
        client.transport_start()
        self.assertEqual(client.transport_state, jack.ROLLING)
        self.assertEqual(libsmf.getPlayState(), PLAYING)
        # Stop
        libsmf.stopPlayback(False)
        self.assertEqual(libsmf.getPlayState(), STOPPING)
        sleep(0.1)
        self.assertEqual(client.transport_state, jack.STOPPED)
        self.assertEqual(libsmf.getPlayState(), STOPPED)


unittest.main()
