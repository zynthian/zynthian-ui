# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_inetradio)
#
# zynthian_engine implementation for internet radio streamer
#
# Copyright (C) 2022-2024 Brian Walton <riban@zynthian.org>
#
# ******************************************************************************
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
# ******************************************************************************

from collections import OrderedDict
import logging
import json
import re
import pexpect
from threading import Thread
from time import sleep

from . import zynthian_engine
import zynautoconnect


# ------------------------------------------------------------------------------
# Internet Radio Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_inet_radio(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Config variables
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, zyngui=None):
        super().__init__(zyngui)
        self.name = "InternetRadio"
        self.nickname = "IR"
        self.jackname = "inetradio"
        self.type = "Audio Generator"
        self.uri = None

        self.monitors_dict = OrderedDict()
        self.monitors_dict['info'] = ""
        self.monitors_dict['audio'] = ""
        self.monitors_dict['codec'] = ""
        self.monitors_dict['bitrate'] = ""
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_inet_radio.py"

        self.cmd = "mplayer -nogui -nolirc -nojoystick -quiet -slave"
        self.command_prompt = "Starting playback..."
        self.proc_timeout = 5
        self.mon_thread = None
        self.handle = 0

        # MIDI Controllers
        self._ctrls = [
            ['volume', None, 50, 100],
            ['stream', None, 'streaming', ['stopped', 'streaming']],
            ['wait for stream', None, 5, 15]
        ]

        # Controller Screens
        self._ctrl_screens = [
            ['main', ['volume', 'stream', 'wait for stream']]
        ]

        self.reset()

    # ---------------------------------------------------------------------------
    # Subproccess Management & IPC
    # ---------------------------------------------------------------------------

    def mon_thread_task(self, handle):
        if self.proc and self.proc.isalive():
            self.proc.sendline('q')
            sleep(0.2)
        if self.proc and self.proc.isalive():
            self.proc.terminate()
            sleep(0.2)
        if self.proc and self.proc.isalive():
            self.proc.terminate(True)
            sleep(0.2)
        self.proc = None

        self.jackname = "inetradio_{}".format(handle)
        self.command = "{} -ao jack:noconnect:name={}".format(
            self.command, self.jackname)
        output = super().start()
        if output:
            self.monitors_dict['info'] = "no info"
            self.update_info(output)
            # Set streaming contoller value
            for processor in self.processors:
                ctrl_dict = processor.controllers_dict
                ctrl_dict['stream'].set_value('streaming', False)
            zynautoconnect.request_audio_connect(True)

            while self.handle == handle:
                sleep(1)
                try:
                    self.proc.expect("\n", timeout=1)
                    res = self.proc.before.decode()
                    self.update_info(res)
                except pexpect.EOF:
                    handle = 0
                except pexpect.TIMEOUT:
                    pass
                except Exception as e:
                    pass
        else:
            self.monitors_dict['info'] = "stream unavailable"

        if self.proc and self.proc.isalive():
            self.proc.sendline('q')
            sleep(0.2)
        if self.proc and self.proc.isalive():
            self.proc.terminate()
            sleep(0.2)
        if self.proc and self.proc.isalive():
            self.proc.terminate(True)
            sleep(0.2)
        self.proc = None
        # Set streaming contoller value
        for processor in self.processors:
            ctrl_dict = processor.controllers_dict
            ctrl_dict['stream'].set_value('stopped', False)

    def update_info(self, output):
        info = re.search("StreamTitle='(.+?)';", output)
        if info:
            self.monitors_dict['info'] = info.group(1)
        info = re.search("\nSelected audio codec: (.+?)\r", output)
        if info:
            self.monitors_dict['codec'] = info.group(1)
        info = re.search("\nAUDIO: (.+?)\r", output)
        if info:
            self.monitors_dict['audio'] = info.group(1)
        info = re.search("\nBitrate: (.+?)\r", output)
        if info:
            self.monitors_dict['bitrate'] = info.group(1)

    def start(self):
        self.handle += 1
        self.monitors_dict['title'] = self.processors[0].preset_name
        self.monitors_dict['info'] = "waiting for stream..."
        self.mon_thread = Thread(
            target=self.mon_thread_task, args=[self.handle])
        self.mon_thread.name = "internet radio {}".format(self.handle)
        self.mon_thread.daemon = True  # thread dies with the program
        self.monitors_dict['codec'] = ""
        self.monitors_dict['audio'] = ""
        self.monitors_dict['bitrate'] = ""
        self.mon_thread.start()

    def stop(self):
        self.handle += 1
        self.mon_thread.join()

        self.monitors_dict['title'] = ""
        self.monitors_dict['info'] = ""
        self.monitors_dict['codec'] = ""
        self.monitors_dict['audio'] = ""
        self.monitors_dict['bitrate'] = ""

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        try:
            with open(self.my_data_dir + "/presets/inet_radio/presets.json", "r") as f:
                self.presets = json.load(f)
        except:
            # Preset file missing or corrupt
            self.presets = {
                "Ambient": [
                    ["http://relax.stream.publicradio.org/relax.mp3",
                        0, "Relax", "auto", ""],
                    ["https://peacefulpiano.stream.publicradio.org/peacefulpiano.aac",
                     0, "Peaceful Piano", "aac", ""],
                    ["http://mp3stream4.abradio.cz/chillout128.mp3",
                     0, "Radio Chillout - ABradio", "auto", ""],
                    ["http://afera.com.pl/afera128.pls",
                     0, "Radio Afera", "auto", ""],
                    ["http://192.111.140.6:8021/listen.pls",
                     0, "Childside Radio", "auto", ""],
                    ["http://usa14.fastcast4u.com/proxy/chillmode",
                     0, "Chillmode Radio", "auto", ""],
                    # ["https://radio.streemlion.com:3590/stream", 0, "Nordic Lodge Copenhagen", "auto", ""]
                ],
                "Classical": [
                    ["http://66.42.114.24:8000/live", 0,
                        "Classical Oasis", "auto", ""],
                    ["https://chambermusic.stream.publicradio.org/chambermusic.aac",
                     0, "Chamber Music", "aac", ""],
                    # ["https://live.amperwave.net/playlist/mzmedia-cfmzfmmp3-ibc2.m3u", 0, "The New Classical FM", "auto", ""],
                    # ["https://audio-mp3.ibiblio.org/wdav-112k", 0, "WDAV Classical: Mozart Café", "auto", ""],
                    # ["https://cast1.torontocast.com:2085/stream", 0, "KISS Classical", "auto", ""]
                ],
                "Techno, Trance, House, D&B": [
                    # ["https://fr1-play.adtonos.com/8105/psystation-minimal", 0, "PsyStation - Minimal Techno", "auto", ""],
                    # ["https://strw3.openstream.co/940", 0, "Minimal & Techno on MixLive.ie", "auto", ""],
                    ["http://stream.radiosputnik.nl:8002/",
                     0, "Radio Sputnik", "auto", ""],
                    ["http://streaming05.liveboxstream.uk:8047/",
                     0, "Select Radio", "auto", ""],
                    ["http://listener3.mp3.tb-group.fm/clt.mp3",
                     0, "ClubTime.FM", "auto", ""],
                    ["http://stream3.jungletrain.net:8000 /;", 0,
                     "jungletrain.net - 24/7 D&B&J", "auto", ""]
                ],
                "Hiphop, R&B, Trap": [
                    # ["https://hiphop24.stream.laut.fm/hiphop24", 0, "HipHop24", "auto", ""],
                    ["http://streams.90s90s.de/hiphop/mp3-192/",
                     0, "90s90s HipHop", "auto", ""],
                    ["https://streams.80s80s.de/hiphop/mp3-192/",
                     0, "80s80s HipHop", "auto", ""],
                    ["http://stream.jam.fm/jamfm-bl/mp3-192/",
                     0, "JAM FM Black Label", "auto", ""],
                    ["http://channels.fluxfm.de/boom-fm-classics/stream.mp3",
                     0, "HipHop Classics", "auto", ""],
                    # ["https: // finesthiphopradio.stream.laut.fm / finesthiphopradio", 0, "Finest HipHop Radio", "auto", ""],
                    # ["https://stream.bigfm.de/oldschoolrap/mp3-128/", 0, "bigFM OLDSCHOOL RAP & HIP-HOP", "auto", ""]
                ],
                "Funk & Soul": [
                    # ["https://funk.stream.laut.fm/funk", 0, "The roots of Funk", "auto", ""],
                    # ["http://radio.pro-fhi.net:2199/rqwrejez.pls", 0, "Funk Power Radio", "auto", ""],
                    ["http://listento.thefunkstation.com:8000",
                     0, "The Funk Station", "auto", ""],
                    ["https://scdn.nrjaudio.fm/adwz1/fr/30607/mp3_128.mp3",
                     0, "Nostalgie Funk", "auto", ""],
                    ["http://funkyradio.streamingmedia.it/play.mp3",
                     0, "Funky Radio", "auto", ""],
                    ["http://listen.shoutcast.com/a-afunk",
                     0, "Anthology Funk", "auto", ""]
                ],
                "Reggae, Afrobeat, World music": [
                    ["http://ais.rastamusic.com/rastamusic.mp3",
                        0, "Rastamusic Reggae Radio ", "auto", ""],
                    ["https://ais-sa2.cdnstream1.com/2294_128.mp3",
                     0, "Big Reggae Mix", "auto", ""],
                    ["http://hd.lagrosseradio.info/lagrosseradio-reggae-192.mp3",
                     0, "La Grosse Radio Reggae", "auto", ""],
                    ["http://api.somafm.com/reggae.pls", 0,
                     "SomaFM: Heavyweight Reggae", "auto", ""],
                    ["http://stream.zenolive.com/n164uxfk8neuv",
                     0, "UbuntuFM Reggae Radio", "auto", ""],
                    ["http://152.228.170.37:8000", 0,
                     "AfroBeats FM", "auto", ""],
                    ["https://wdr-cosmo-afrobeat.icecastssl.wdr.de/wdr/cosmo/afrobeat/mp3/128/stream.mp3",
                     0, "WDR Cosmo - Afrobeat", "auto", ""],
                    ["http://stream.zenolive.com/erfqvd71nd5tv",
                     0, "Rainbow Radio", "auto", ""],
                    ["http://usa6.fastcast4u.com:5374/", 0,
                     "Rainbow Radio - UK", "auto", ""],
                    ["http://topjam.ddns.net:8100/", 0,
                     "TOP JAM Radio Reggae Dancehall", "auto", ""],
                    ["http://stream.jam.fm/jamfm_afrobeats/mp3-192/",
                     0, "JAM FM Afrobeats", "auto", ""]
                ],
                "Jazz & Blues": [
                    ["http://jazzblues.ice.infomaniak.ch/jazzblues-high.mp3",
                        0, "Jazz Blues", "auto", ""],
                    ["http://live.amperwave.net/direct/ppm-jazz24mp3-ibc1",
                     0, "Jazz24 - KNKX-HD2", "auto", ""],
                    ["http://stream.sublime.nl/web24_mp3",
                     0, "Sublime Classics", "auto", ""],
                    ["http://jazz-wr01.ice.infomaniak.ch/jazz-wr01-128.mp3",
                     0, "JAZZ RADIO CLASSIC JAZZ", "auto", ""],
                    ["http://jzr-piano.ice.infomaniak.ch/jzr-piano.mp3",
                     0, "JAZZ RADIO PIANO JAZZ", "auto", ""],
                    ["http://stream.radio.co/s7c1ea5960/listen",
                     0, "Capital Jazz Radio", "auto", ""],
                    ["http://radio.wanderingsheep.tv:8000/jazzcafe",
                     0, "Jazz Cafe", "auto", ""],
                    ["https://jazz.stream.laut.fm/jazz",
                     0, "Ministry of Soul", "auto", ""],
                    ["https://stream.spreeradio.de/deluxe/mp3-192/",
                     0, "105‘5 Spreeradio Deluxe", "auto", ""]
                ],
                "Latin & Afrocuban": [
                    ["https://ny.mysonicserver.com/9918/stream",
                        0, "La esquina del guaguanco", "auto", ""],
                    ["http://tropicalisima.net:8020", 0,
                     "Tropicalisima FM Salsa", "auto", ""],
                    ["https://salsa.stream.laut.fm/salsa",
                     0, "Salsa", "auto", ""],
                    ["http://95.216.22.117:8456/stream",
                     0, "Hola NY Salsa", "auto", ""],
                    ["http://stream.zeno.fm/r82w6dp09vzuv",
                     0, "Salseros", "auto", ""],
                    ["http://stream.zenolive.com/tgzmw19rqrquv",
                     0, "Salsa.fm", "auto", ""],
                    ["http://stream.zenolive.com/u27pdewuq74tv",
                     0, "Salsa Gorda Radio", "auto", ""],
                    # ["https://salsa-high.rautemusik.fm/", 0, "RauteMusik SALSA", "auto", ""],
                    # ["https://centova.streamingcastrd.net/proxy/bastosalsa/stream", 0, "Basto Salsa Radio", "auto", ""],
                    # ["https://usa15.fastcast4u.com/proxy/erenteri", 0, "Radio Salsa Online", "auto", ""],
                    # ["https://cloudstream2036.conectarhosting.com:8242", 0, "La Makina del Sabor", "auto", ""],
                    # ["https://cloudstream2032.conectarhosting.com/8122/stream", 0, "Salsa Magistral", "auto", ""],
                    # ["https://cloud8.vsgtech.co/8034/stream", 0, "Viva la salsa", "auto", ""],
                    # ["https://cast1.my-control-panel.com/proxy/salsason/stream", 0, "Salsa con Timba", "auto", ""],
                ],
                "Pop & Rock": [
                    ["http://icy.unitedradio.it/VirginRock70.mp3",
                        0, "Virgin Rock 70's", "auto", ""],
                    ["http://sc3.radiocaroline.net:8030/listen.m3u",
                     0, "Radio Caroline", "auto", ""]
                ],
                "Miscellaneous": [
                    ["http://stream.radiotime.com/listen.m3u?streamId=10555650",
                        0, "FIP", "auto", ""],
                    ["http://icecast.radiofrance.fr/fipgroove-hifi.aac",
                     0, "FIP Groove", "aac", ""],
                    ["http://direct.fipradio.fr/live/fip-webradio4.mp3",
                     0, "FIP Radio 4", "auto", ""],
                ]
            }
        self.banks = []
        for bank in self.presets:
            self.banks.append([bank, None, bank, None])
        return self.banks

    # ---------------------------------------------------------------------------
    # Preset Management
    # ---------------------------------------------------------------------------

    def get_preset_list(self, bank):
        presets = []
        for preset in self.presets[bank[0]]:
            presets.append(preset)
        return presets

    def set_preset(self, processor, preset, preload=False):
        if self.uri == preset[0]:
            return
        self.uri = preset[0]
        demux = preset[3]
        volume = None
        for processor in self.processors:
            try:
                ctrl_dict = processor.controllers_dict
                volume = ctrl_dict['volume'].value
                break
            except:
                pass
        if volume is None:
            volume = 50
        self.command = "{} -volume {}".format(self.cmd, volume)
        if self.uri.endswith("m3u") or self.uri.endswith("pls"):
            self.command += " -playlist"
        if demux and demux != 'auto':
            self.command += " -demuxer {}".format(demux)
        self.command += " {}".format(self.uri)
        self.start()

    # ----------------------------------------------------------------------------
    # Controllers Management
    # ----------------------------------------------------------------------------

    def get_controllers_dict(self, processor):
        dict = super().get_controllers_dict(processor)
        return dict

    def send_controller_value(self, zctrl):
        if zctrl.symbol == "volume":
            if self.proc:
                self.proc.sendline("volume {} 1".format(zctrl.value))
        elif zctrl.symbol == "stream":
            if zctrl.value == 0:
                self.stop()
            elif self.proc == None:
                self.start()
        elif zctrl.symbol == "wait for stream":
            self.proc_timeout = zctrl.value

    def get_monitors_dict(self):
        return self.monitors_dict

    # ---------------------------------------------------------------------------
    # Specific functions
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

# ******************************************************************************
