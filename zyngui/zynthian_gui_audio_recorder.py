#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio Recorder Class
# 
# Copyright (C) 2015-2018 Fernando Moyano <jofemodo@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

import os
import sys
import logging
import mutagen
import threading
from time import sleep
from os.path import isfile, isdir, join, basename
from subprocess import check_output, Popen, PIPE

# Zynthian specific modules
import zynconf
from . import zynthian_gui_config
from . import zynthian_gui_selector
from . import zynthian_gui_controller
from zyngine import zynthian_controller

#------------------------------------------------------------------------------
# Zynthian Audio Recorder GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_audio_recorder(zynthian_gui_selector):
	
	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")
	mplayer_ctrl_fifo_path = "/tmp/mplayer-control"

	def __init__(self):
		self.capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture"
		self.capture_dir_usb = os.environ.get('ZYNTHIAN_EX_DATA_DIR',"/media/usb0")
		self.current_playback_fpath = None
		self.rec_proc = None
		self.play_proc = None

		super().__init__('Audio Recorder', True)

		self.volume_zctrl = zynthian_controller(self, "volume", "Volume", {
			'value': 60,
			'value_min': 0,
			'value_max': 100,
			'is_toggle': False,
			'is_integer': False
		})
		self.volume_zgui_ctrl = None


	def hide(self):
		super().hide()
		if self.volume_zgui_ctrl:
			self.volume_zgui_ctrl.hide()


	def get_status(self):
		status=None

		if self.rec_proc:
			status="REC"

		if self.current_playback_fpath:
			if status=="REC":
				status="PLAY+REC"
			else:
				status="PLAY"

		return status


	def fill_list(self):
		#self.index=0
		self.list_data=[]

		status=self.get_status()
		if status=="REC" or status=="PLAY+REC":
			self.list_data.append(("STOP_RECORDING",0,"Stop Recording"))
		else:
			self.list_data.append(("START_RECORDING",0,"Start Recording"))

		#if status=="PLAY" or status=="PLAY+REC":
		#	self.list_data.append(("STOP_PLAYING",0,"Stop Playing"))
		#	self.show_playing_volume()

		if zynthian_gui_config.audio_play_loop:
			self.list_data.append(("LOOP",0,"[x] Loop Play"))
		else:
			self.list_data.append(("LOOP",0,"[  ] Loop Play"))

		self.list_data.append((None,0,"-----------------------------"))

		i=1
		# Files on SD-Card
		for fname, finfo in self.get_filelist(self.capture_dir_sdc).items():
			l = finfo['length']
			title="SD[{}:{:02d}] {}".format(int(l/60), int(l%60),fname.replace(";",">",1).replace(";","/"))
			self.list_data.append((finfo['fpath'],i,title))
			i+=1

		# Files on USB-Pendrive
		for fname, finfo in self.get_filelist(self.capture_dir_usb).items():
			l = finfo['length']
			title="USB[{}:{:02d}] {}".format(int(l/60), int(l%60),fname.replace(";",">",1).replace(";","/"))
			self.list_data.append((finfo['fpath'],i,title))
			i+=1

		super().fill_list()


	def get_filelist(self, src_dir):
		res = {}
		for f in sorted(os.listdir(src_dir)):
			fpath = join(src_dir, f)
			fname = f[:-4]
			fext = f[-4:].lower()
			if isfile(fpath) and fext in ('.wav', '.mp3', '.ogg'):
				if fname in res:
					if fext=='.wav':
						res[fname]['ext'] = fext
					elif fext=='.ogg' and res[fname]['ext']!='.wav':
						res[fname]['ext'] = fext
				else:	
					res[fname] = {
						'fpath': fpath,
						'ext': fext
					}

		for fname in res:
			try:
				res[fname]['length'] = mutagen.File(res[fname]['fpath']).info.length
			except Exception as e:
				res[fname]['length'] = 0
				logging.warning(e)

		return res


	def fill_listbox(self):
		super().fill_listbox()
		self.highlight()


	# Highlight command and current record played, if any ...
	def highlight(self):
		for i, row in enumerate(self.list_data):
			if row[0] is not None and row[0]==self.current_playback_fpath:
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_hl})
			else:
				self.listbox.itemconfig(i, {'fg':zynthian_gui_config.color_panel_tx})


	def select_action(self, i, t='S'):
		fpath=self.list_data[i][0]

		if fpath=="START_RECORDING":
			self.start_recording()
		elif fpath=="STOP_PLAYING":
			self.stop_playing()
		elif fpath=="STOP_RECORDING":
			self.stop_recording()
		elif fpath=="LOOP":
			self.toggle_loop()
		elif fpath:
			if t=='S':
				self.toggle_playing(fpath)
			else:
				self.zyngui.show_confirm("Do you really want to delete '{}'?".format(self.list_data[i][2]), self.delete_confirmed, fpath)


	def get_next_filenum(self):
		try:
			n = max(map(lambda item: int(os.path.basename(item[0])[0:3]) if item[0] and os.path.basename(item[0])[0:3].isdigit() else 0, self.list_data))
		except:
			n = 0
		return "{0:03d}".format(n+1)


	def get_new_filename(self):
		try:
			parts = self.zyngui.curlayer.get_presetpath().split('#',2)
			file_name = parts[1].replace("/",";").replace(">",";").replace(" ; ",";")
		except:
			file_name = "jack_capture"
		return self.get_next_filenum() + '-' + file_name + '.wav'


	def delete_confirmed(self, fpath):
		logging.info("DELETE AUDIO RECORDING: {}".format(fpath))
		for ext in ("wav", "ogg", "mp3"):
			try:
				os.remove("{}.{}".format(fpath[:-4],ext))
			except Exception as e:
				#logging.error(e)
				pass
		self.zyngui.show_modal("audio_recorder")


	def start_recording(self):
		if self.get_status() not in ("REC", "PLAY+REC"):
			logging.info("STARTING NEW AUDIO RECORD ...")
			try:
				capture_dir = "/media/usb0"
				check_mount = Popen(("/bin/mountpoint", "-q", "--", capture_dir))
				if check_mount.wait() != 0:
					capture_dir = "/zynthian/zynthian-my-data/capture"
					try:
						os.mkdir(capture_dir)
					except:
						pass
				self.rec_proc = Popen(("/usr/local/bin/jack_capture", "--daemon", self.get_new_filename()), cwd=capture_dir)				
			except Exception as e:
				logging.error("ERROR STARTING AUDIO RECORD: %s" % e)
				self.zyngui.show_info("ERROR STARTING AUDIO RECORD:\n %s" % e)
				self.zyngui.hide_info_timer(5000)

			self.update_list()
			return True

		else:
			return False


	def stop_recording(self):
		if self.get_status() in ("REC", "PLAY+REC"):
			logging.info("STOPPING AUDIO RECORD ...")
			try:
				self.rec_proc.terminate()
				self.rec_proc = None
			except Exception as e:
				logging.error("ERROR STOPPING AUDIO RECORD: %s" % e)
				self.zyngui.show_info("ERROR STOPPING AUDIO RECORD:\n %s" % e)
				self.zyngui.hide_info_timer(5000)

			self.update_list()
			return True

		else:
			return False


	def toggle_recording(self):
		logging.info("TOGGLING AUDIO RECORDING ...")
		if not self.stop_recording():
			self.start_recording()


	def start_playing(self, fpath=None):
		self.stop_playing()

		if fpath is None:
			fpath = self.get_current_track_fpath()
		
		if fpath is None:
			logging.info("No track to play!")
			return

		logging.info("STARTING AUDIO PLAY '{}' ...".format(fpath))

		# Create control fifo is needed ...
		try:
			os.mkfifo(self.mplayer_ctrl_fifo_path)
		except:
			pass

		try:
			if zynthian_gui_config.audio_play_loop:
				cmd="/usr/bin/mplayer -nogui -noconsolecontrols -nolirc -nojoystick -really-quiet -slave -loop 0 -ao jack -input file=\"{}\" \"{}\"".format(self.mplayer_ctrl_fifo_path, fpath)
			else:
				cmd="/usr/bin/mplayer -nogui -noconsolecontrols -nolirc -nojoystick -really-quiet -slave -ao jack -input file=\"{}\" \"{}\"".format(self.mplayer_ctrl_fifo_path, fpath)

			logging.info("COMMAND: %s" % cmd)

			def runInThread(onExit, cmd):
				self.play_proc = Popen(cmd, shell=True, universal_newlines=True)
				self.play_proc.wait()
				self.end_playing()
				return

			thread = threading.Thread(target=runInThread, args=(self.end_playing, cmd), daemon=True)
			thread.start()
			sleep(0.5)
			self.zyngui.zynautoconnect_audio()
			self.show_playing_volume()
			self.send_controller_value(self.volume_zctrl)
			self.current_playback_fpath=fpath

		except Exception as e:
			logging.error("ERROR STARTING AUDIO PLAY: %s" % e)
			self.zyngui.show_info("ERROR STARTING AUDIO PLAY:\n %s" % e)
			self.zyngui.hide_info_timer(5000)

		self.update_list()
		return True


	def send_mplayer_command(self, cmd):
		with open(self.mplayer_ctrl_fifo_path, "w") as f:
			f.write(cmd + "\n")
			f.close()


	def end_playing(self):
		logging.info("ENDING AUDIO PLAY ...")
		self.play_proc = None
		self.current_playback_fpath=None
		self.volume_zgui_ctrl.hide()
		self.update_list()


	def stop_playing(self):
		if self.get_status() in ("PLAY", "PLAY+REC"):
			logging.info("STOPPING AUDIO PLAY ...")
			try:
				self.send_mplayer_command("quit")
				while self.play_proc:
					sleep(0.1)
			except Exception as e:
				logging.error("ERROR STOPPING AUDIO PLAY: %s" % e)
				self.zyngui.show_info("ERROR STOPPING AUDIO PLAY:\n %s" % e)
				self.zyngui.hide_info_timer(5000)
			return True

		else:
			return False


	def toggle_playing(self, fpath=None):
		logging.info("TOGGLING AUDIO PLAY ...")
		self.stop_playing()
		if fpath and fpath!=self.current_playback_fpath:
			self.start_playing(fpath)


	def show_playing_volume(self):
		if self.volume_zgui_ctrl:
			self.volume_zgui_ctrl.config(self.volume_zctrl)
			self.volume_zgui_ctrl.show()
		else:
			self.volume_zgui_ctrl = zynthian_gui_controller(2, self.main_frame, self.volume_zctrl)


	# Implement engine's method
	def send_controller_value(self, zctrl):
		if zctrl.symbol=="volume":
			self.send_mplayer_command("volume {} 1".format(zctrl.value))
			logging.debug("SET PLAYING VOLUME => {}".format(zctrl.value))


	def zyncoder_read(self):
		super().zyncoder_read()
		if self.shown and self.volume_zgui_ctrl:
			self.volume_zgui_ctrl.read_zyncoder()
		return [0,1]


	def plot_zctrls(self):
		super().plot_zctrls()
		if self.volume_zgui_ctrl:
			self.volume_zgui_ctrl.plot_value()


	def get_current_track_fpath(self):
		# Fill list if it's empty ...
		if not self.list_data:
			self.fill_list()
		#if selected track ...
		if self.list_data[self.index][1]>0:
			return self.list_data[self.index][0]
		#return last track if there is one ...
		elif self.list_data[-1][1]>0:
			return self.list_data[-1][0]
		#else return None
		else:
			return None


	def toggle_loop(self):
		if zynthian_gui_config.audio_play_loop:
			logging.info("Audio play loop OFF")
			zynthian_gui_config.audio_play_loop=False
		else:
			logging.info("Audio play loop ON")
			zynthian_gui_config.audio_play_loop=True
		zynconf.save_config({"ZYNTHIAN_AUDIO_PLAY_LOOP": str(int(zynthian_gui_config.audio_play_loop))})
		self.update_list()


	def set_select_path(self):
		self.select_path.set("Audio Recorder")

#------------------------------------------------------------------------------
