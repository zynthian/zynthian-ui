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
                self.client.setblocking(False)
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
                    buffer += self.client.recv(1024)
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
                    ["https://radio.streemlion.com:3590/stream", 0, "Nordic Lodge Copenhagen", "auto", ""]
                ],
                "Classical": [
                    ["http://66.42.114.24:8000/live", 0,
                        "Classical Oasis", "auto", ""],
                    ["https://chambermusic.stream.publicradio.org/chambermusic.aac",
                     0, "Chamber Music", "aac", ""],
                    ["https://live.amperwave.net/playlist/mzmedia-cfmzfmmp3-ibc2.m3u", 0, "The New Classical FM", "auto", ""],
                    ["https://audio-mp3.ibiblio.org/wdav-112k", 0, "WDAV Classical: Mozart Café", "auto", ""],
                    ["https://cast1.torontocast.com:2085/stream", 0, "KISS Classical", "auto", ""]
                ],
                "Techno, Trance, House, D&B": [
                    ["https://fr1-play.adtonos.com/8105/psystation-minimal", 0, "PsyStation - Minimal Techno", "auto", ""],
                    ["https://strw3.openstream.co/940", 0, "Minimal & Techno on MixLive.ie", "auto", ""],
                    ["http://stream.radiosputnik.nl:8002/",
                     0, "Radio Sputnik", "auto", ""],
                    ["http://streaming05.liveboxstream.uk:8047/",
                     0, "Select Radio", "auto", ""],
                    ["http://listener3.mp3.tb-group.fm/clt.mp3",
                     0, "ClubTime.FM", "auto", ""],
                    #["http://stream3.jungletrain.net:8000 /;", 0,
                    # "jungletrain.net - 24/7 D&B&J", "auto", ""]
                ],
                "Hiphop, R&B, Trap": [
                    ["https://hiphop24.stream.laut.fm/hiphop24", 0, "HipHop24", "auto", ""],
                    ["http://streams.90s90s.de/hiphop/mp3-192/",
                     0, "90s90s HipHop", "auto", ""],
                    ["https://streams.80s80s.de/hiphop/mp3-192/",
                     0, "80s80s HipHop", "auto", ""],
                    ["http://stream.jam.fm/jamfm-bl/mp3-192/",
                     0, "JAM FM Black Label", "auto", ""],
                    ["http://channels.fluxfm.de/boom-fm-classics/stream.mp3",
                     0, "HipHop Classics", "auto", ""],
                    ["https: // finesthiphopradio.stream.laut.fm / finesthiphopradio", 0, "Finest HipHop Radio", "auto", ""],
                    ["https://stream.bigfm.de/oldschoolrap/mp3-128/", 0, "bigFM OLDSCHOOL RAP & HIP-HOP", "auto", ""]
                ],
                "Funk & Soul": [
                    ["https://funk.stream.laut.fm/funk", 0, "The roots of Funk", "auto", ""],
                    ["http://radio.pro-fhi.net:2199/rqwrejez.pls", 0, "Funk Power Radio", "auto", ""],
                    ["http://listento.thefunkstation.com:8000",
                     0, "The Funk Station", "auto", ""],
                    #["https://scdn.nrjaudio.fm/adwz1/fr/30607/mp3_128.mp3",
                    # 0, "Nostalgie Funk", "auto", ""],
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
                    # Silent stream ["http://stream.sublime.nl/web24_mp3",
                    # 0, "Sublime Classics", "auto", ""],
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
                    #["https://salsa-high.rautemusik.fm/", 0, "RauteMusik SALSA", "auto", ""],
                    ["https://centova.streamingcastrd.net/proxy/bastosalsa/stream", 0, "Basto Salsa Radio", "auto", ""],
                    ["https://usa15.fastcast4u.com/proxy/erenteri", 0, "Radio Salsa Online", "auto", ""],
                    #["https://cloudstream2036.conectarhosting.com:8242", 0, "La Makina del Sabor", "auto", ""],
                    #["https://cloudstream2032.conectarhosting.com/8122/stream", 0, "Salsa Magistral", "auto", ""],
                    ["https://cloud8.vsgtech.co/8034/stream", 0, "Viva la salsa", "auto", ""],
                    ["https://cast1.my-control-panel.com/proxy/salsason/stream", 0, "Salsa con Timba", "auto", ""],
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
        self.preset2bank = []
        for bank_i, bank in enumerate(self.presets):
            self.banks.append([bank, None, bank, None])
            for preset_i, preset in enumerate(self.presets[bank]):
                self.preset2bank.append((bank_i, preset_i, preset[2]))

        playlists = []
        for file in listdir(f"{self.my_data_dir}/capture"):
            if file[-4:].lower() in (".m3u", ".pls"):
                playlists.append([f"{self.my_data_dir}/capture/{file}", 1, file[:-4], "auto", ""])
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
