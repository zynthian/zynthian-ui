#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Unit tests for zynaudioplayer
# Tests use two letters to define order of groups and two digit integer to define order within group

import unittest
import jack
from time import sleep

import zynaudioplayer

client = jack.Client("zynaudioplayer_unittest")

STOPPED		= 0
STARTING	= 1
PLAYING		= 2
STOPPING	= 3

class TestLibZynAudioPlayer(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        pass

    @classmethod
    def tearDownClass(self):
        pass

    def test_aa00_debug(self):
       libaudioplayer.enableDebug(True)
       libaudioplayer.enableDebug(False)

    def test_aa01_load(self):
        self.assertTrue(zynaudioplayer.load("./test.wav")) #TODO: Add test.wav

    def test_aa02_duration(self):
        self.assertTrue(zynaudioplayer.load("./test.wav"))
        self.assertEqual(libaudioplayer.getDuration(), 6125) #TODO: Set correct duration for test

    def test_aa03_position(self):
        self.assertTrue(zynaudioplayer.load("./test.wav"))
        libsmf.setPosition(2000)
        self.assertEqual(libaudioplayer.getPosition(), 2000)

    def test_aa04_channels(self):
        self.assertTrue(zynaudioplayer.load("./test.wav"))
        self.assertEqual(libaudioplayer.getChannels(), 2)

    def test_aa05_format_wav(self):
        self.assertTrue(zynaudioplayer.load("./test.wav"))
        self.assertEqual(libaudioplayer.getFormat(), 0x010000 | 0x0002) #TODO: Check test wav file format

    def test_aa05_format_ogg(self):
        self.assertTrue(zynaudioplayer.load("./test.wav"))
        self.assertEqual(libaudioplayer.getFormat(), 0x010000 | 0x0002) #TODO: Check test wav file format


unittest.main()
