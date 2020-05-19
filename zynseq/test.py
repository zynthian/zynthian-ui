#!/usr/bin/python3

import jack
import ctypes
from os.path import dirname, realpath

client = jack.Client("riban")

#libzynseq=ctypes.CDLL(dirname(realpath(__file__))+"/build/libzynseq.so")
libzynseq=ctypes.CDLL("./libzynseq.so")

libzynseq.init()

#libzynseq.load(b"mypatterns.zynseq")
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

