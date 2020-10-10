#!/usr/bin/python3

import jack
from os.path import dirname, realpath
import ctypes

libzynseq=ctypes.CDLL("./libzynseq.so")

client = jack.Client("riban")
client.midi_inports.register('input')

#libzynseq=ctypes.CDLL(dirname(realpath(__file__))+"/build/libzynseq.so")

libzynseq.init()

def testLoad():
	libzynseq.load(b"./test.zynseq")

def testSave():
	libzynseq.save(b"./test.zynseq")

def testSong():
	libzynseq.selectSong(1)
	print("Get tracks (expect 0):", libzynseq.getTracks())
	for track in range(1,5):
		libzynseq.addTrack()
	print("Get tracks (expect 4):", libzynseq.getTracks())
	print("Get tempo (expect 120):", libzynseq.getTempo())
	libzynseq.setTempo(100)
	print("Get tempo (expect 100):", libzynseq.getTempo())
	print("Get grid size (expect 4):", libzynseq.getGridSize())
	libzynseq.setGridSize(6)
	print("Get grid size (expect 6):", libzynseq.getGridSize())
	print("Get tracks (expect 4):", libzynseq.getTracks())
	for track in range(0,libzynseq.getTracks()):
		print("Get track sequence (expect %d): %d" % (track+1, libzynseq.getSequence(track)))

def testTransport():
	libzynseq.selectPattern(0)
	print("Steps in selected pattern", libzynseq.getSteps())
	#libzynseq.save(b"mypatterns.zynseq")

	#client.connect("jack_midi_clock:mclk_out", "zynthstep:input")
	#client.transport_stop()
	#client.transport_start()

	libzynseq.addNote(0, 60, 100, 2)
	libzynseq.addNote(2, 62, 127, 1)
	libzynseq.addPattern(0, 0, 0)

	libzynseq.setTempo(60)

	libzynseq.debug(True)
	#libzynseq.debug(False)

	# Start sequence 0
	#libzynseq.setPlayMode(0, 1)
	#libzynseq.setPlayMode(0, 0)
	#libzynseq.clearSequence(0)


