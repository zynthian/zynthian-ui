# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_inetradio)
#
# zynthian_engine implementation for internet radio streamer
#
# Copyright (C) 2022-2025 Brian Walton <riban@zynthian.org>
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
from subprocess import Popen, STDOUT, PIPE
import socket
from threading import Thread, Timer
from os.path import basename
from os import listdir
from time import sleep, monotonic

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

        self.preset = None # Currently selected preset
        self.preset2bank = [] # List of (bank index, preset index, preset name) for prev/next optimisation
        self.preset_i = 0 # Index of current preset in preset2bank list
        self.pending_preset_i = 0 # Index of preselected pending preset
        self.pending_preset_ts = 0 # Timeout to select pending preset
        self.client = None # Telnet client to vlc
        self.connect_timer = None # Timer to trigger autoconnect

        self.monitors_dict = OrderedDict()
        self.monitors_dict['reset'] = True
        self.monitors_dict['title'] = ""
        self.monitors_dict['info'] = ""
        self.monitors_dict['channels'] = ""
        self.monitors_dict['codec'] = ""
        self.monitors_dict['bitrate'] = ""
        self.monitors_dict['url'] = ""
        self.monitors_dict['reset'] = False
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_inet_radio.py"

        self.command = ["vlc",
                        "--intf", "telnet",
                        "--telnet-password", "zynthian",
                        "--aout", "jack",
                        "--jack-connect-regex", ":::",
                        "--jack-name", self.jackname,
                        "--no-audio-time-stretch"
                        ]

        # MIDI Controllers
        self._ctrls = [
            ['volume', None, 80, 100],
            ['stream', None, 'streaming', ['stopped', 'streaming']],
            ['prev/next', None, '<>', ['<', '<>', '>']],
            ['pause', None, 'playing', ['paused', 'playing']],
            ['random', None, 'off', ['off', 'on']]
        ]

        # Controller Screens
        self._ctrl_screens = [
            ['main', ['volume', 'stream', 'prev/next', 'pause']]
        ]

        self.start()

    # ---------------------------------------------------------------------------
    # Subproccess Management & IPC
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        return super().add_processor(processor)

    def start(self):
        if not self.proc:
            logging.info("Starting Engine {}".format(self.name))
            try:
                logging.debug("Command: {}".format(self.command))
                # Turns out that environment's PWD is not set automatically
                # when cwd is specified for pexpect.spawn(), so do it here.
                if self.command_cwd:
                    self.command_env['PWD'] = self.command_cwd
                # Setting cwd is because we've set PWD above. Some engines doesn't
                # care about the process's cwd, but it is more consistent to set
                # cwd when PWD has been set.
                self.command_env['DISPLAY'] = ":-1" # Disable display of GUI to enable CLI
                self.proc = Popen(self.command, env=self.command_env, cwd=self.command_cwd, shell=False,
                                  text=True, bufsize=1, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
                sleep(1)
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(1)
                self.client.connect(("localhost", 4212)) #TODO Assign port in config
                self.client.recv(4096)
                self.client.send("zynthian\n".encode())
                self.start_proc_poll_thread()
                
            except Exception as err:
                logging.error(
                    "Can't start engine {} => {}".format(self.name, err))

    def stop(self):
        if self.proc:
            try:
                logging.info("Stopping Engine " + self.name)
                self.proc_cmd("shutdown")
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except:
                    self.proc.kill()
                self.proc = None
            except Exception as err:
                logging.error(f"Can't stop engine {self.name} => {err}")

    def start_proc_poll_thread(self):
        self.proc_poll_thread = Thread(target=self.proc_poll_thread_task, args=())
        self.proc_poll_thread.name = f"proc_poll_{self.jackname}"
        self.proc_poll_thread.daemon = True  # thread dies with the program
        self.proc_poll_thread.start()

    def proc_cmd(self, cmd):
        if self.client:
            self.client.send(f"{cmd}\n".encode())

    def proc_poll_thread_task(self):
        last_status = 0
        last_info = 0
        line = ""
        while self.proc.poll() is None:
            now = monotonic()
            if self.preset_i == self.pending_preset_i:
                if now > last_info + 5:
                    self.proc_cmd("info")
                    last_info = now
                if now > last_status + 1:
                    self.proc_cmd("status")
                    last_status = now
            buffer = bytes()
            while True:
                try:
                    response = self.client.recv(1024)
                    buffer += response
                    if response == b'':
                        break
                except TimeoutError:
                    break
            if buffer:
                for i, c in enumerate(buffer):
                    if c == 13:
                        # newline
                        self.proc_poll_parse_line(line)
                        line = ""
                        buffer = buffer[i:]
                    elif c < 32 or c > 126:
                        continue
                    else:
                        line += chr(c)
                if line:
                    self.proc_poll_parse_line(line)
            if self.pending_preset_i != self.preset_i and now > self.pending_preset_ts:
                self.processors[0].set_bank(self.preset2bank[self.pending_preset_i][0])
                self.processors[0].load_preset_list()
                self.processors[0].set_preset(self.preset2bank[self.pending_preset_i][1])

    def reset_monitors(self, reset_title=False):
        for key in self.monitors_dict:
            if reset_title or key != "title":
                self.monitors_dict[key] = ""

    def proc_poll_parse_line(self, line):
        if line.startswith(">"):
            line = line[1:]
        line = line.strip()
        if line.startswith("| now_playing:"):
            value = line[14:]
            try:
                x = value.strip().split("~")
                self.monitors_dict['info'] = "\n".join(x[:4])
            except:
                self.monitors_dict['info'] = ""
        elif line.startswith("| filename:"):
            if not self.preset[1] and not self.monitors_dict["info"]:
                self.monitors_dict["info"] = basename(line[11:].strip())
        elif line.startswith("( new input:"):
            url = line[12:-1].strip()
            if self.monitors_dict["url"] != url:
                self.delayed_connect_outputs()
                self.reset_monitors()
            self.monitors_dict["url"] = url
            self.monitors_dict["reset"] = True
        elif line.startswith("| album:"):
            self.monitors_dict["info"] = f"{line[8:].strip()}\n\n"
        elif line.startswith("| artist:"):
            self.monitors_dict["info"] += f"{line[9:].strip()}\n"
        else:
            for key in ("title", "Name", "Genre", "Website", "Bitrate", "Channels", "Sample rate", "Codec"):
                if line.startswith(f"| {key}:"):
                    try:
                        self.monitors_dict[key.lower()] = line.split(":")[1].strip()
                    except:
                        pass
                    break


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
                        0, "Relax"],
                    ["https://peacefulpiano.stream.publicradio.org/peacefulpiano.aac",
                     0, "Peaceful Piano", "aac", ""],
                    ["http://mp3stream4.abradio.cz/chillout128.mp3",
                     0, "Radio Chillout - ABradio"],
                    ["http://afera.com.pl/afera128.pls",
                     0, "Radio Afera"],
                    ["http://192.111.140.6:8021/listen.pls",
                     0, "Childside Radio"],
                    ["http://usa14.fastcast4u.com/proxy/chillmode",
                     0, "Chillmode Radio"],
                    ["https://radio.streemlion.com:3590/stream", 0, "Nordic Lodge Copenhagen"]
                ],
                "Classical": [
                    ["http://66.42.114.24:8000/live", 0,
                        "Classical Oasis"],
                    ["https://chambermusic.stream.publicradio.org/chambermusic.aac",
                     0, "Chamber Music", "aac", ""],
                    ["https://live.amperwave.net/playlist/mzmedia-cfmzfmmp3-ibc2.m3u", 0, "The New Classical FM"],
                    ["https://audio-mp3.ibiblio.org/wdav-112k", 0, "WDAV Classical: Mozart Café"],
                    ["https://cast1.torontocast.com:2085/stream", 0, "KISS Classical"]
                ],
                "Techno, Trance, House, D&B": [
                    ["https://fr1-play.adtonos.com/8105/psystation-minimal", 0, "PsyStation - Minimal Techno"],
                    ["https://strw3.openstream.co/940", 0, "Minimal & Techno on MixLive.ie"],
                    ["http://stream.radiosputnik.nl:8002/",
                     0, "Radio Sputnik"],
                    ["http://streaming05.liveboxstream.uk:8047/",
                     0, "Select Radio"],
                    ["http://listener3.mp3.tb-group.fm/clt.mp3",
                     0, "ClubTime.FM"],
                    #["http://stream3.jungletrain.net:8000 /;", 0,
                    # "jungletrain.net - 24/7 D&B&J"]
                ],
                "Hiphop, R&B, Trap": [
                    ["https://hiphop24.stream.laut.fm/hiphop24", 0, "HipHop24"],
                    ["http://streams.90s90s.de/hiphop/mp3-192/",
                     0, "90s90s HipHop"],
                    ["https://streams.80s80s.de/hiphop/mp3-192/",
                     0, "80s80s HipHop"],
                    ["http://stream.jam.fm/jamfm-bl/mp3-192/",
                     0, "JAM FM Black Label"],
                    ["http://channels.fluxfm.de/boom-fm-classics/stream.mp3",
                     0, "HipHop Classics"],
                    ["https: // finesthiphopradio.stream.laut.fm / finesthiphopradio", 0, "Finest HipHop Radio"],
                    ["https://stream.bigfm.de/oldschoolrap/mp3-128/", 0, "bigFM OLDSCHOOL RAP & HIP-HOP"]
                ],
                "Funk & Soul": [
                    ["https://funk.stream.laut.fm/funk", 0, "The roots of Funk"],
                    ["http://radio.pro-fhi.net:2199/rqwrejez.pls", 0, "Funk Power Radio"],
                    ["http://listento.thefunkstation.com:8000",
                     0, "The Funk Station"],
                    #["https://scdn.nrjaudio.fm/adwz1/fr/30607/mp3_128.mp3",
                    # 0, "Nostalgie Funk"],
                    ["http://funkyradio.streamingmedia.it/play.mp3",
                     0, "Funky Radio"],
                    ["http://listen.shoutcast.com/a-afunk",
                     0, "Anthology Funk"]
                ],
                "Reggae, Afrobeat, World music": [
                    ["http://ais.rastamusic.com/rastamusic.mp3",
                        0, "Rastamusic Reggae Radio "],
                    ["https://ais-sa2.cdnstream1.com/2294_128.mp3",
                     0, "Big Reggae Mix"],
                    ["http://hd.lagrosseradio.info/lagrosseradio-reggae-192.mp3",
                     0, "La Grosse Radio Reggae"],
                    ["http://api.somafm.com/reggae.pls", 0,
                     "SomaFM: Heavyweight Reggae"],
                    ["http://stream.zenolive.com/n164uxfk8neuv",
                     0, "UbuntuFM Reggae Radio"],
                    ["http://152.228.170.37:8000", 0,
                     "AfroBeats FM"],
                    ["https://wdr-cosmo-afrobeat.icecastssl.wdr.de/wdr/cosmo/afrobeat/mp3/128/stream.mp3",
                     0, "WDR Cosmo - Afrobeat"],
                    ["http://stream.zenolive.com/erfqvd71nd5tv",
                     0, "Rainbow Radio"],
                    ["http://usa6.fastcast4u.com:5374/", 0,
                     "Rainbow Radio - UK"],
                    ["http://topjam.ddns.net:8100/", 0,
                     "TOP JAM Radio Reggae Dancehall"],
                    ["http://stream.jam.fm/jamfm_afrobeats/mp3-192/",
                     0, "JAM FM Afrobeats"]
                ],
                "Jazz & Blues": [
                    ["http://jazzblues.ice.infomaniak.ch/jazzblues-high.mp3",
                        0, "Jazz Blues"],
                    ["http://live.amperwave.net/direct/ppm-jazz24mp3-ibc1",
                     0, "Jazz24 - KNKX-HD2"],
                    # Silent stream ["http://stream.sublime.nl/web24_mp3",
                    # 0, "Sublime Classics"],
                    ["http://jazz-wr01.ice.infomaniak.ch/jazz-wr01-128.mp3",
                     0, "JAZZ RADIO CLASSIC JAZZ"],
                    ["http://jzr-piano.ice.infomaniak.ch/jzr-piano.mp3",
                     0, "JAZZ RADIO PIANO JAZZ"],
                    ["http://stream.radio.co/s7c1ea5960/listen",
                     0, "Capital Jazz Radio"],
                    ["http://radio.wanderingsheep.tv:8000/jazzcafe",
                     0, "Jazz Cafe"],
                    ["https://jazz.stream.laut.fm/jazz",
                     0, "Ministry of Soul"],
                    ["https://stream.spreeradio.de/deluxe/mp3-192/",
                     0, "105‘5 Spreeradio Deluxe"]
                ],
                "Latin & Afrocuban": [
                    ["https://ny.mysonicserver.com/9918/stream",
                        0, "La esquina del guaguanco"],
                    ["http://tropicalisima.net:8020", 0,
                     "Tropicalisima FM Salsa"],
                    ["https://salsa.stream.laut.fm/salsa",
                     0, "Salsa"],
                    ["http://95.216.22.117:8456/stream",
                     0, "Hola NY Salsa"],
                    ["http://stream.zeno.fm/r82w6dp09vzuv",
                     0, "Salseros"],
                    ["http://stream.zenolive.com/tgzmw19rqrquv",
                     0, "Salsa.fm"],
                    ["http://stream.zenolive.com/u27pdewuq74tv",
                     0, "Salsa Gorda Radio"],
                    #["https://salsa-high.rautemusik.fm/", 0, "RauteMusik SALSA"],
                    ["https://centova.streamingcastrd.net/proxy/bastosalsa/stream", 0, "Basto Salsa Radio"],
                    ["https://usa15.fastcast4u.com/proxy/erenteri", 0, "Radio Salsa Online"],
                    #["https://cloudstream2036.conectarhosting.com:8242", 0, "La Makina del Sabor"],
                    #["https://cloudstream2032.conectarhosting.com/8122/stream", 0, "Salsa Magistral"],
                    ["https://cloud8.vsgtech.co/8034/stream", 0, "Viva la salsa"],
                    ["https://cast1.my-control-panel.com/proxy/salsason/stream", 0, "Salsa con Timba"],
                ],
                "Pop & Rock": [
                    ["http://icy.unitedradio.it/VirginRock70.mp3",
                        0, "Virgin Rock 70's"],
                    ["http://sc3.radiocaroline.net:8030/listen.m3u",
                     0, "Radio Caroline"]
                ],
                "Miscellaneous": [
                    ["http://stream.radiotime.com/listen.m3u?streamId=10555650",
                        0, "FIP"],
                    ["http://icecast.radiofrance.fr/fipgroove-hifi.aac",
                     0, "FIP Groove", "aac", ""],
                    ["http://direct.fipradio.fr/live/fip-webradio4.mp3",
                     0, "FIP Radio 4"],
                ],
                "BBC": [
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_one&bitrate=96000",
                        0,
                        "BBC Radio 1"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_1xtra&bitrate=96000",
                        0,
                        "BBC Radio 1Xtra"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_one_dance&bitrate=96000",
                        0,
                        "BBC Radio 1 Dance"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_one_anthems&bitrate=96000&uk=1",
                        0,
                        "BBC Radio 1 Anthems (UK Only)"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_two&bitrate=96000",
                        0,
                        "BBC Radio 2"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_three&bitrate=96000",
                        0,
                        "BBC Radio 3"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_three_unwind&bitrate=96000&uk=1",
                        0,
                        "BBC Radio 3 Unwind (UK Only)"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_fourfm&bitrate=96000",
                        0,
                        "BBC Radio 4"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_four_extra&bitrate=96000",
                        0,
                        "BBC Radio 4 Extra"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_five_live&bitrate=96000",
                        0,
                        "BBC Radio 5 Live"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_6music&bitrate=96000",
                        0,
                        "BBC Radio 6 Music"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_five_live_sports_extra&bitrate=96000&uk=1",
                        0,
                        "BBC Radio Sports Extra (UK Only)"
                    ],
                    [
                        "https://as-hls-uk.live.cf.md.bbci.co.uk/pool_24041977/live/uk/bbc_radio_five_sports_extra_2/bbc_radio_five_sports_extra_2.isml/bbc_radio_five_sports_extra_2-audio%3d320000.norewind.m3u8",
                        0,
                        "BBC Radio Sports Extra 2 (UK Only)"
                    ],
                    [
                        "https://as-hls-uk.live.cf.md.bbci.co.uk/pool_02012018/live/uk/bbc_radio_five_sports_extra_3/bbc_radio_five_sports_extra_3.isml/bbc_radio_five_sports_extra_3-audio%3d320000.norewind.m3u8",
                        0,
                        "BBC Radio Sports Extra 3 (UK Only)"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_asian_network&bitrate=96000",
                        0,
                        "BBC Asian Network"
                    ],
                    [
                        "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service",
                        0,
                        "BBC World Service (English)"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_coventry_warwickshire&bitrate=96000",
                        0,
                        "BBC CWR"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_essex&bitrate=96000",
                        0,
                        "BBC Essex"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_hereford_worcester&bitrate=96000",
                        0,
                        "BBC Hereford & Worcester"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_berkshire&bitrate=96000",
                        0,
                        "BBC Radio Berkshire"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_bristol&bitrate=96000",
                        0,
                        "BBC Radio Britsol"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_cambridge&bitrate=96000",
                        0,
                        "BBC Radio Cambridge"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_cornwall&bitrate=96000",
                        0,
                        "BBC Radio Cornwall"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_cumbria&bitrate=96000",
                        0,
                        "BBC Radio Cumbria"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_cymru&bitrate=96000",
                        0,
                        "BBC Radio Cymru"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_cymru_2&bitrate=96000",
                        0,
                        "BBC Radio Cymru 2"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_derby&bitrate=96000",
                        0,
                        "BBC Radio Derby"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_devon&bitrate=96000",
                        0,
                        "BBC Radio Devon"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_foyle&bitrate=96000",
                        0,
                        "BBC Radio Foyle"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_gloucestershire&bitrate=96000",
                        0,
                        "BBC Radio Gloucestershire"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_guernsey&bitrate=96000",
                        0,
                        "BBC Radio Guernsey"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_humberside&bitrate=96000",
                        0,
                        "BBC Radio Humberside"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_jersey&bitrate=96000",
                        0,
                        "BBC Radio Jersey"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_kent&bitrate=96000",
                        0,
                        "BBC Radio Kent"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_lancashire&bitrate=96000",
                        0,
                        "BBC Radio Lancashire"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_leeds&bitrate=96000",
                        0,
                        "BBC Radio Leeds"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_leicester&bitrate=96000",
                        0,
                        "BBC Radio Leicester"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_lincolnshire&bitrate=96000",
                        0,
                        "BBC Radio Lincolnshire"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_london&bitrate=96000",
                        0,
                        "BBC Radio London"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_manchester&bitrate=96000",
                        0,
                        "BBC Radio Manchester"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_merseyside&bitrate=96000",
                        0,
                        "BBC Radio Merseyside"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_nan_gaidheal&bitrate=96000",
                        0,
                        "BBC Radio nan G\u00e0idheal"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_newcastle&bitrate=96000",
                        0,
                        "BBC Radio Newcastle"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_norfolk&bitrate=96000",
                        0,
                        "BBC Radio Norfolk"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_northampton&bitrate=96000",
                        0,
                        "BBC Radio Northampton"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_nottingham&bitrate=96000",
                        0,
                        "BBC Radio Nottingham"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_orkney&bitrate=96000",
                        0,
                        "BBC Radio Orkney"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_oxford&bitrate=96000",
                        0,
                        "BBC Radio Oxford"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_scotland_fm&bitrate=96000",
                        0,
                        "BBC Radio Scotland FM"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_scotland_mw&bitrate=96000",
                        0,
                        "BBC Radio Scotland MW"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_sheffield&bitrate=96000",
                        0,
                        "BBC Radio Sheffield"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_shropshire&bitrate=96000",
                        0,
                        "BBC Radio Shropshire"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_solent&bitrate=96000",
                        0,
                        "BBC Radio Solent"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_solent_west_dorset&bitrate=96000",
                        0,
                        "BBC Radio Solent West Dorset"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_somerset_sound&bitrate=96000",
                        0,
                        "BBC Radio Somerset Sound"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_stoke&bitrate=96000",
                        0,
                        "BBC Radio Stoke"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_suffolk&bitrate=96000",
                        0,
                        "BBC Radio Suffolk"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_surrey&bitrate=96000",
                        0,
                        "BBC Radio Surrey"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_sussex&bitrate=96000",
                        0,
                        "BBC Radio Sussex"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_tees&bitrate=96000",
                        0,
                        "BBC Radio Tees"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_ulster&bitrate=96000",
                        0,
                        "BBC Radio Ulster"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_wales_fm&bitrate=96000",
                        0,
                        "BBC Radio Wales"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_wiltshire&bitrate=96000",
                        0,
                        "BBC Radio Wiltshire"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_wm&bitrate=96000",
                        0,
                        "BBC Radio WM"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_radio_york&bitrate=96000",
                        0,
                        "BBC Radio York"
                    ],
                    [
                        "http://lsn.lv/bbcradio.m3u8?station=bbc_three_counties_radio&bitrate=96000",
                        0,
                        "BBC Three Counties Radio"
                    ]
                ]
            }
            """
            # Write default preset file
            json_obj = json.dumps(self.presets, indent=4)
            with open(self.my_data_dir + "/presets/inet_radio/presets.json", "w") as f:
                f.write(json_obj)
            """

        self.banks = []
        self.preset2bank = []
        for bank_i, bank in enumerate(self.presets):
            self.banks.append([bank, None, bank, None])
            for preset_i, preset in enumerate(self.presets[bank]):
                self.preset2bank.append((bank_i, preset_i, preset[2]))

        playlists = []
        for file in listdir(f"{self.my_data_dir}/capture"):
            if file[-4:].lower() in (".m3u", ".pls"):
                playlists.append([f"{self.my_data_dir}/capture/{file}", 1, file[:-4]])
        if playlists:
            self.presets["Playlists"] = playlists
            self.banks.append(["Playlists", None, "Playlists", None])

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
        self.preset = preset
        for self.preset_i, config in enumerate(self.preset2bank):
            if config[0] == processor.bank_index and config[1] == processor.preset_index:
                break
        self.pending_preset_i = self.preset_i
        self.proc_cmd("clear")
        self.proc_cmd(f"add {preset[0]}")
        self.monitors_dict['title'] = preset[2]
        if preset[1]:
            self._ctrl_screens = [
                ['main', ['volume', 'stream', 'prev/next', 'pause']],
                ['playlist', ['random']]
            ]
        else:
            self._ctrl_screens = [['main', ['volume', 'stream', 'prev/next']]]
        processor.refresh_controllers()
        self.reset_monitors()
        self.delayed_connect_outputs()

    def delayed_connect_outputs(self):
        """ Trigger background delayed audio autoconnect, incase other mechanisms fail"""
        sleep(0.2)
        zynautoconnect.request_audio_connect(True)
        if self.connect_timer:
            self.connect_timer.cancel()
        self.connect_timer = Timer(2, zynautoconnect.audio_autoconnect)
        self.connect_timer.start()
        
    # ----------------------------------------------------------------------------
    # Controllers Management
    # ----------------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        if self.proc is None:
            return
        if zctrl.symbol == "volume":
                self.proc_cmd(f"volume {zctrl.value * 3}")
        elif zctrl.symbol == "prev/next":
            value = zctrl.value - 1
            zctrl.set_value(1, False)
            if self.preset:
                if self.preset[1]:
                    if value > 0:
                        self.proc_cmd(f"next")
                    elif value < 0:
                        self.proc_cmd(f"prev")
                    self.reset_monitors(True)
                    self.proc_cmd("info")
                    sleep(0.2)
                    zynautoconnect.request_audio_connect(True)
                    self.delayed_connect_outputs()
                else:
                    pending_preset = self.pending_preset_i + value
                    if pending_preset < 0 or pending_preset >= len(self.preset2bank):
                        return
                    self.pending_preset_i = pending_preset
                    self.pending_preset_ts = monotonic() + 1
                    self.monitors_dict['title'] = f"<{self.preset2bank[self.pending_preset_i][2]}>"
                    self.monitors_dict['reset'] = True
                    return
        elif zctrl.symbol == "stream":
            if zctrl.value:
                self.proc_cmd("play")
                self.monitors_dict["url"] = ""
                self.delayed_connect_outputs()
            else:
                self.proc_cmd("stop")
        elif zctrl.symbol == "pause":
            # Cannot set absolute pause mode so force pause then toggle
            if zctrl.value:
                self.proc_cmd("play")
            else:
                self.proc_cmd("pause")
        elif zctrl.symbol == "random":
            if zctrl.value:
                self.proc_cmd("random on")
            else:
                self.proc_cmd("random off")
        return

    def get_monitors_dict(self):
        return self.monitors_dict

    # ---------------------------------------------------------------------------
    # Specific functions
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------

# ******************************************************************************
