#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Admin Class
# 
# Copyright (C) 2015-2016 Fernando Moyano <jofemodo@zynthian.org>
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
import re
import sys
import signal
import logging
from time import sleep
from threading  import Thread
from subprocess import check_output, Popen, PIPE, STDOUT

# Zynthian specific modules
import zynconf
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#-------------------------------------------------------------------------------
# Zynthian Admin GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_admin(zynthian_gui_selector):

	data_dir = os.environ.get('ZYNTHIAN_DATA_DIR',"/zynthian/zynthian-data")
	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")


	def __init__(self):
		self.commands=None
		self.thread=None
		self.child_pid=None
		self.last_action=None

		super().__init__('Action', True)

		if self.zyngui.allow_rbpi_headphones():
			self.default_rbpi_headphones()

		self.default_vncserver()


	def fill_list(self):
		self.list_data=[]

		if self.zyngui.allow_rbpi_headphones():
			if zynthian_gui_config.rbpi_headphones:
				self.list_data.append((self.stop_rbpi_headphones,0,"[x] RBPi Headphones"))
			else:
				self.list_data.append((self.start_rbpi_headphones,0,"[  ] RBPi Headphones"))

		if zynthian_gui_config.midi_single_active_channel:
			self.list_data.append((self.toggle_single_channel,0,"->  Stage Mode (Omni-On)"))
		else:
			self.list_data.append((self.toggle_single_channel,0,"=>  Multi-timbral Mode"))

		if zynthian_gui_config.midi_prog_change_zs3:
			self.list_data.append((self.toggle_prog_change_zs3,0,"[x] Program Change ZS3"))
		else:
			self.list_data.append((self.toggle_prog_change_zs3,0,"[  ] Program Change ZS3"))

		if zynthian_gui_config.midi_bank_change:
			self.list_data.append((self.toggle_bank_change,0,"[x] MIDI Bank Change"))
		else:
			self.list_data.append((self.toggle_bank_change,0,"[  ] MIDI Bank Change"))

		if zynthian_gui_config.preset_preload_noteon:
			self.list_data.append((self.toggle_preset_preload_noteon,0,"[x] Preset Preload"))
		else:
			self.list_data.append((self.toggle_preset_preload_noteon,0,"[  ] Preset Preload"))

		if zynthian_gui_config.snapshot_mixer_settings:
			self.list_data.append((self.toggle_snapshot_mixer_settings,0,"[x] Audio Levels on Snapshots"))
		else:
			self.list_data.append((self.toggle_snapshot_mixer_settings,0,"[  ] Audio Levels on Snapshots"))

		if zynthian_gui_config.midi_filter_output:
			self.list_data.append((self.toggle_midi_filter_output,0,"[x] Route MIDI to Output"))
		else:
			self.list_data.append((self.toggle_midi_filter_output,0,"[  ] Route MIDI to Output"))

		if zynthian_gui_config.midi_sys_enabled:
			self.list_data.append((self.toggle_midi_sys,0,"[x] MIDI System Messages"))
		else:
			self.list_data.append((self.toggle_midi_sys,0,"[  ] MIDI System Messages"))

		if zynconf.is_service_active("jackrtpmidid"):
			self.list_data.append((self.stop_rtpmidi,0,"[x] RTP-MIDI"))
		else:
			self.list_data.append((self.start_rtpmidi,0,"[  ] RTP-MIDI"))

		if zynconf.is_service_active("qmidinet"):
			self.list_data.append((self.stop_qmidinet,0,"[x] QmidiNet (IP Multicast)"))
		else:
			self.list_data.append((self.start_qmidinet,0,"[  ] QmidiNet (IP Multicast)"))

		if zynconf.is_service_active("touchosc2midi"):
			self.list_data.append((self.stop_touchosc2midi,0,"[x] TouchOSC MIDI Bridge"))
		else:
			self.list_data.append((self.start_touchosc2midi,0,"[  ] TouchOSC MIDI Bridge"))

		if zynconf.is_service_active("aubionotes"):
			self.list_data.append((self.stop_aubionotes,0,"[x] AubioNotes (Audio2MIDI)"))
		else:
			self.list_data.append((self.start_aubionotes,0,"[  ] AubioNotes (Audio2MIDI)"))

		self.list_data.append((self.midi_profile,0,"MIDI Profile"))

		self.list_data.append((None,0,"-----------------------------"))
		self.list_data.append((self.network_info,0,"Network Info"))

		if zynconf.is_wifi_active():
			if zynconf.is_service_active("hostapd"):
				self.list_data.append((self.stop_wifi,0,"[x] Wi-Fi Hotspot"))
			else:
				self.list_data.append((self.stop_wifi,0,"[x] Wi-Fi"))
		else:
			self.list_data.append((self.start_wifi,0,"[  ] Wi-Fi"))
			self.list_data.append((self.start_wifi_hotspot,0,"[  ] Wi-Fi Hotspot"))

		if zynconf.is_service_active("vncserver0"):
			self.list_data.append((self.stop_vncserver,0,"[x] VNC Server"))
		else:
			self.list_data.append((self.start_vncserver,0,"[  ] VNC Server"))

		self.list_data.append((None,0,"-----------------------------"))
		self.list_data.append((self.test_audio,0,"Test Audio"))
		self.list_data.append((self.test_midi,0,"Test MIDI"))
		self.list_data.append((None,0,"-----------------------------"))
		self.list_data.append((self.zyngui.calibrate_touchscreen,0,"Calibrate Touchscreen"))
		if self.is_update_available():
			self.list_data.append((self.update_software,0,"Update Software"))
		else:
			self.list_data.append((self.check_for_updates,0,"Check for software updates"))
		#self.list_data.append((self.update_system,0,"Update Operating System"))
		self.list_data.append((None,0,"-----------------------------"))
		self.list_data.append((self.restart_gui,0,"Restart UI"))
		#self.list_data.append((self.exit_to_console,0,"Exit to Console"))
		self.list_data.append((self.reboot,0,"Reboot"))
		self.list_data.append((self.power_off,0,"Power Off"))
		super().fill_list()


	def show(self):
		super().show()


	def select_action(self, i, t='S'):
		if self.list_data[i][0]:
			self.last_action=self.list_data[i][0]
			self.last_action()


	def set_select_path(self):
		self.select_path.set("Admin")


	def execute_commands(self):
		self.zyngui.start_loading()
		
		error_counter=0
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			self.zyngui.add_info("EXECUTING:\n","EMPHASIS")
			self.zyngui.add_info("{}\n".format(cmd))
			try:
				self.proc=Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
				self.zyngui.add_info("RESULT:\n","EMPHASIS")
				for line in self.proc.stdout:
					if re.search("ERROR", line, re.IGNORECASE):
						error_counter+=1
						tag="ERROR"
					elif re.search("Already", line, re.IGNORECASE):
						tag="SUCCESS"
					else:
						tag=None
					logging.info(line.rstrip())
					self.zyngui.add_info(line,tag)
				self.zyngui.add_info("\n")
			except Exception as e:
				logging.error(e)
				self.zyngui.add_info("ERROR: %s\n" % e, "ERROR")

		if error_counter>0:
			logging.info("COMPLETED WITH {} ERRORS!".format(error_counter))
			self.zyngui.add_info("COMPLETED WITH {} ERRORS!".format(error_counter), "WARNING")
		else:
			logging.info("COMPLETED OK!")
			self.zyngui.add_info("COMPLETED OK!", "SUCCESS")

		self.commands=None
		self.zyngui.add_info("\n\n")
		self.zyngui.hide_info_timer(5000)
		self.zyngui.stop_loading()


	def start_command(self,cmds):
		if not self.commands:
			logging.info("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.execute_commands, args=())
			self.thread.name = "command sequence"
			self.thread.daemon = True # thread dies with the program
			self.thread.start()


	def killable_execute_commands(self):
		#self.zyngui.start_loading()
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			self.zyngui.add_info("EXECUTING:\n","EMPHASIS")
			self.zyngui.add_info("{}\n".format(cmd))
			try:
				proc=Popen(cmd.split(" "), stdout=PIPE, stderr=PIPE)
				self.child_pid=proc.pid
				self.zyngui.add_info("\nPID: %s" % self.child_pid)
				(output, error)=proc.communicate()
				self.child_pid=None
				if error:
					result="ERROR: %s" % error
					logging.error(result)
					self.zyngui.add_info(result,"ERROR")
				if output:
					logging.info(output)
					self.zyngui.add_info(output)
			except Exception as e:
				result="ERROR: %s" % e
				logging.error(result)
				self.zyngui.add_info(result,"ERROR")

		self.commands=None
		self.zyngui.hide_info_timer(5000)
		#self.zyngui.stop_loading()


	def killable_start_command(self,cmds):
		if not self.commands:
			logging.info("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.killable_execute_commands, args=())
			self.thread.name = "killable command sequence"
			self.thread.daemon = True # thread dies with the program
			self.thread.start()


	def kill_command(self):
		if self.child_pid:
			logging.info("Killing process %s" % self.child_pid)
			os.kill(self.child_pid, signal.SIGTERM)
			self.child_pid=None
			if self.last_action==self.test_midi:
				self.zyngui.all_sounds_off()

	#------------------------------------------------------------------------------
	# CONFIG OPTIONS
	#------------------------------------------------------------------------------

	def start_rbpi_headphones(self, save_config=True):
		logging.info("STARTING RBPI HEADPHONES")

		try:
			check_output("systemctl start headphones", shell=True)
			zynthian_gui_config.rbpi_headphones = 1
			# Update Config
			if save_config:
				zynconf.save_config({ 
					"ZYNTHIAN_RBPI_HEADPHONES": str(zynthian_gui_config.rbpi_headphones)
				})
			# Call autoconnect after a little time
			sleep(0.5)
			self.zyngui.zynautoconnect_audio()

		except Exception as e:
			logging.error(e)

		self.fill_list()


	def stop_rbpi_headphones(self, save_config=True):
		logging.info("STOPPING RBPI HEADPHONES")

		try:
			check_output("systemctl stop headphones", shell=True)
			zynthian_gui_config.rbpi_headphones = 0
			# Update Config
			if save_config:
				zynconf.save_config({ 
					"ZYNTHIAN_RBPI_HEADPHONES": str(int(zynthian_gui_config.rbpi_headphones))
				})

		except Exception as e:
			logging.error(e)

		self.fill_list()


	#Start/Stop RBPI Headphones depending on configuration
	def default_rbpi_headphones(self):
		if zynthian_gui_config.rbpi_headphones:
			self.start_rbpi_headphones(False)
		else:
			self.stop_rbpi_headphones(False)


	def toggle_snapshot_mixer_settings(self):
		if zynthian_gui_config.snapshot_mixer_settings:
			logging.info("Mixer Settings on Snapshots OFF")
			zynthian_gui_config.snapshot_mixer_settings=False
		else:
			logging.info("Mixer Settings on Snapshots ON")
			zynthian_gui_config.snapshot_mixer_settings=True

		# Update Config
		zynconf.save_config({ 
			"ZYNTHIAN_UI_SNAPSHOT_MIXER_SETTINGS": str(int(zynthian_gui_config.snapshot_mixer_settings))
		})

		self.fill_list()


	def toggle_midi_filter_output(self):
		if zynthian_gui_config.midi_filter_output:
			logging.info("MIDI Filter Output OFF")
			zynthian_gui_config.midi_filter_output=False
		else:
			logging.info("MIDI Filter Output ON")
			zynthian_gui_config.midi_filter_output=True

		# Update MIDI profile
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_FILTER_OUTPUT": str(int(zynthian_gui_config.midi_filter_output))
		})

		self.zyngui.zynautoconnect_midi()
		self.fill_list()


	def toggle_midi_sys(self):
		if zynthian_gui_config.midi_sys_enabled:
			logging.info("MIDI System Messages OFF")
			zynthian_gui_config.midi_sys_enabled=False
		else:
			logging.info("MIDI System Messages ON")
			zynthian_gui_config.midi_sys_enabled=True

		# Update MIDI profile
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_SYS_ENABLED": str(int(zynthian_gui_config.midi_sys_enabled))
		})

		lib_zyncore.set_midi_filter_system_events(zynthian_gui_config.midi_sys_enabled)
		self.fill_list()


	def toggle_single_channel(self):
		if zynthian_gui_config.midi_single_active_channel:
			logging.info("Single Channel Mode OFF")
			zynthian_gui_config.midi_single_active_channel=False
		else:
			logging.info("Single Channel Mode ON")
			zynthian_gui_config.midi_single_active_channel=True

		# Update MIDI profile
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_SINGLE_ACTIVE_CHANNEL": str(int(zynthian_gui_config.midi_single_active_channel))
		})

		self.zyngui.set_active_channel()
		sleep(0.5)
		self.fill_list()


	def toggle_prog_change_zs3(self):
		if zynthian_gui_config.midi_prog_change_zs3:
			logging.info("ZS3 Program Change OFF")
			zynthian_gui_config.midi_prog_change_zs3=False
		else:
			logging.info("ZS3 Program Change ON")
			zynthian_gui_config.midi_prog_change_zs3=True

		# Save config
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_PROG_CHANGE_ZS3": str(int(zynthian_gui_config.midi_prog_change_zs3))
		})

		self.fill_list()


	def toggle_bank_change(self):
		if zynthian_gui_config.midi_bank_change:
			logging.info("MIDI Bank Change OFF")
			zynthian_gui_config.midi_bank_change=False
		else:
			logging.info("MIDI Bank Change ON")
			zynthian_gui_config.midi_bank_change=True

		# Save config
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_BANK_CHANGE": str(int(zynthian_gui_config.midi_bank_change))
		})

		self.fill_list()


	def toggle_preset_preload_noteon(self):
		if zynthian_gui_config.preset_preload_noteon:
			logging.info("Preset Preload OFF")
			zynthian_gui_config.preset_preload_noteon=False
		else:
			logging.info("Preset Preload ON")
			zynthian_gui_config.preset_preload_noteon=True

		# Save config
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON": str(int(zynthian_gui_config.preset_preload_noteon))
		})

		self.fill_list()



	def start_qmidinet(self, save_config=True):
		logging.info("STARTING QMIDINET")

		try:
			check_output("systemctl start qmidinet", shell=True)
			zynthian_gui_config.midi_network_enabled = 1
			# Update MIDI profile
			if save_config:
				zynconf.update_midi_profile({ 
					"ZYNTHIAN_MIDI_NETWORK_ENABLED": str(zynthian_gui_config.midi_network_enabled)
				})
			# Call autoconnect after a little time
			sleep(0.5)
			self.zyngui.zynautoconnect_midi()

		except Exception as e:
			logging.error(e)

		self.fill_list()


	def stop_qmidinet(self, save_config=True):
		logging.info("STOPPING QMIDINET")

		try:
			check_output("systemctl stop qmidinet", shell=True)
			zynthian_gui_config.midi_network_enabled = 0
			# Update MIDI profile
			if save_config:
				zynconf.update_midi_profile({ 
					"ZYNTHIAN_MIDI_NETWORK_ENABLED": str(zynthian_gui_config.midi_network_enabled)
				})

		except Exception as e:
			logging.error(e)

		self.fill_list()


	#Start/Stop QMidiNet depending on configuration
	def default_qmidinet(self):
		if zynthian_gui_config.midi_network_enabled:
			self.start_qmidinet(False)
		else:
			self.stop_qmidinet(False)


	def start_rtpmidi(self, save_config=True):
		logging.info("STARTING RTP-MIDI")

		try:
			check_output("systemctl start jackrtpmidid", shell=True)
			zynthian_gui_config.midi_rtpmidi_enabled = 1
			# Update MIDI profile
			if save_config:
				zynconf.update_midi_profile({ 
					"ZYNTHIAN_MIDI_RTPMIDI_ENABLED": str(zynthian_gui_config.midi_rtpmidi_enabled)
				})
			# Call autoconnect after a little time
			sleep(0.5)
			self.zyngui.zynautoconnect_midi()

		except Exception as e:
			logging.error(e)

		self.fill_list()


	def stop_rtpmidi(self, save_config=True):
		logging.info("STOPPING RTP-MIDI")

		try:
			check_output("systemctl stop jackrtpmidid", shell=True)
			zynthian_gui_config.midi_rtpmidi_enabled = 0
			# Update MIDI profile
			if save_config:
				zynconf.update_midi_profile({ 
					"ZYNTHIAN_MIDI_RTPMIDI_ENABLED": str(zynthian_gui_config.midi_rtpmidi_enabled)
				})

		except Exception as e:
			logging.error(e)

		self.fill_list()


	#Start/Stop RTP-MIDI depending on configuration
	def default_rtpmidi(self):
		if zynthian_gui_config.midi_rtpmidi_enabled:
			self.start_rtpmidi(False)
		else:
			self.stop_rtpmidi(False)


	def start_touchosc2midi(self, save_config=True):
		logging.info("STARTING touchosc2midi")
		try:
			check_output("systemctl start touchosc2midi", shell=True)
			zynthian_gui_config.midi_touchosc_enabled = 1
			# Update MIDI profile
			if save_config:
				zynconf.update_midi_profile({ 
					"ZYNTHIAN_MIDI_TOUCHOSC_ENABLED": str(zynthian_gui_config.midi_touchosc_enabled)
				})
			# Call autoconnect after a little time
			sleep(0.5)
			self.zyngui.zynautoconnect_midi()

		except Exception as e:
			logging.error(e)

		self.fill_list()


	def stop_touchosc2midi(self, save_config=True):
		logging.info("STOPPING touchosc2midi")
		try:
			check_output("systemctl stop touchosc2midi", shell=True)
			zynthian_gui_config.midi_touchosc_enabled = 0
			# Update MIDI profile
			if save_config:
				zynconf.update_midi_profile({ 
					"ZYNTHIAN_MIDI_TOUCHOSC_ENABLED": str(zynthian_gui_config.midi_touchosc_enabled)
				})

		except Exception as e:
			logging.error(e)

		self.fill_list()


	#Start/Stop TouchOSC depending on configuration
	def default_touchosc(self):
		if zynthian_gui_config.midi_touchosc_enabled:
			self.start_touchosc2midi(False)
		else:
			self.stop_touchosc2midi(False)


	def start_aubionotes(self, save_config=True):
		logging.info("STARTING aubionotes")
		try:
			check_output("systemctl start aubionotes", shell=True)
			zynthian_gui_config.midi_aubionotes_enabled = 1
			# Update MIDI profile
			if save_config:
				zynconf.update_midi_profile({ 
					"ZYNTHIAN_MIDI_AUBIONOTES_ENABLED": str(zynthian_gui_config.midi_aubionotes_enabled)
				})
			# Call autoconnect after a little time
			sleep(0.5)
			self.zyngui.zynautoconnect()

		except Exception as e:
			logging.error(e)

		self.fill_list()


	def stop_aubionotes(self, save_config=True):
		logging.info("STOPPING aubionotes")
		try:
			check_output("systemctl stop aubionotes", shell=True)
			zynthian_gui_config.midi_aubionotes_enabled = 0
			# Update MIDI profile
			if save_config:
				zynconf.update_midi_profile({ 
					"ZYNTHIAN_MIDI_AUBIONOTES_ENABLED": str(zynthian_gui_config.midi_aubionotes_enabled)
				})

		except Exception as e:
			logging.error(e)

		self.fill_list()


	#Start/Stop AubioNotes depending on configuration
	def default_aubionotes(self):
		if zynthian_gui_config.midi_aubionotes_enabled:
			self.start_aubionotes(False)
		else:
			self.stop_aubionotes(False)


	def midi_profile(self):
		logging.info("MIDI Profile")
		self.zyngui.show_screen("midi_profile")

#------------------------------------------------------------------------------
# NETWORK FEATURES
#------------------------------------------------------------------------------

	def network_info(self):
		self.zyngui.show_info("NETWORK INFO\n")

		res = zynconf.network_info()
		for k, v in res.items():
			self.zyngui.add_info(" {} => {}\n".format(k,v[0]),v[1])

		self.zyngui.hide_info_timer(5000)
		self.zyngui.stop_loading()


	def start_wifi(self):
		if not zynconf.start_wifi():
			self.zyngui.show_info("STARTING WIFI ERROR\n")
			self.zyngui.add_info("Can't start WIFI network!","WARNING")
			self.zyngui.hide_info_timer(2000)

		self.fill_list()


	def start_wifi_hotspot(self):
		if not zynconf.start_wifi_hotspot():
			self.zyngui.show_info("STARTING WIFI HOTSPOT ERROR\n")
			self.zyngui.add_info("Can't start WIFI Hotspot!","WARNING")
			self.zyngui.hide_info_timer(2000)

		self.fill_list()


	def stop_wifi(self):
		if not zynconf.stop_wifi():
			self.zyngui.show_info("STOPPING WIFI ERROR\n")
			self.zyngui.add_info("Can't stop WIFI network!","WARNING")
			self.zyngui.hide_info_timer(2000)

		self.fill_list()


	def start_vncserver(self, save_config=True):
		# Start VNC for Zynthian-UI
		if not zynconf.is_service_active("vncserver0"):
			self.zyngui.start_loading()

			try:
				logging.info("STARTING VNC-UI SERVICE")
				check_output("systemctl start novnc0", shell=True)
				zynthian_gui_config.vncserver_enabled = 1
			except Exception as e:
				logging.error(e)

			self.zyngui.stop_loading()

		# Start VNC for Engine's native GUIs
		if not zynconf.is_service_active("vncserver1"):
			self.zyngui.start_loading()

			# Save state and stop engines
			if len(self.zyngui.screens['layer'].layers)>0:
				self.zyngui.screens['snapshot'].save_last_state_snapshot()
				restore_state = True
			else:
				restore_state = False

			try:
				logging.info("STARTING VNC-ENGINES SERVICE")
				check_output("systemctl start novnc1", shell=True)
				zynthian_gui_config.vncserver_enabled = 1
			except Exception as e:
				logging.error(e)

			# Restore state
			if restore_state:
				self.zyngui.screens['snapshot'].load_last_state_snapshot()

			self.zyngui.stop_loading()

		# Update Config
		if save_config:
			zynconf.save_config({ 
				"ZYNTHIAN_VNCSERVER_ENABLED": str(zynthian_gui_config.vncserver_enabled)
			})

		self.fill_list()


	def stop_vncserver(self, save_config=True):
		# Stop VNC for Zynthian-UI
		if zynconf.is_service_active("vncserver0"):
			self.zyngui.start_loading()

			try:
				logging.info("STOPPING VNC-UI SERVICE")
				check_output("systemctl stop vncserver0", shell=True)
				zynthian_gui_config.vncserver_enabled = 0
			except Exception as e:
				logging.error(e)

			self.zyngui.stop_loading()

		# Start VNC for Engine's native GUIs
		if zynconf.is_service_active("vncserver1"):
			self.zyngui.start_loading()

			# Save state and stop engines
			if len(self.zyngui.screens['layer'].layers)>0:
				self.zyngui.screens['snapshot'].save_last_state_snapshot()
				restore_state = True
			else:
				restore_state = False

			try:
				logging.info("STOPPING VNC-ENGINES SERVICE")
				check_output("systemctl stop vncserver1", shell=True)
				zynthian_gui_config.vncserver_enabled = 0
			except Exception as e:
				logging.error(e)

			# Restore state
			if restore_state:
				self.zyngui.screens['snapshot'].load_last_state_snapshot()
				
			self.zyngui.stop_loading()

		# Update Config
		if save_config:
			zynconf.save_config({ 
				"ZYNTHIAN_VNCSERVER_ENABLED": str(zynthian_gui_config.vncserver_enabled)
			})

		self.fill_list()


	#Start/Stop VNC Server depending on configuration
	def default_vncserver(self):
		if zynthian_gui_config.vncserver_enabled:
			self.start_vncserver(False)
		else:
			self.stop_vncserver(False)


#------------------------------------------------------------------------------
# SYSTEM FEATURES
#------------------------------------------------------------------------------

	def test_audio(self):
		logging.info("TESTING AUDIO")
		self.zyngui.show_info("TEST AUDIO")
		#self.killable_start_command(["mpg123 {}/audio/test.mp3".format(self.data_dir)])
		self.killable_start_command(["mplayer -nogui -noconsolecontrols -nolirc -nojoystick -really-quiet -ao jack {}/audio/test.mp3".format(self.data_dir)])
		sleep(0.5)
		self.zyngui.zynautoconnect_audio()


	def test_midi(self):
		logging.info("TESTING MIDI")
		self.zyngui.show_info("TEST MIDI")
		self.killable_start_command(["aplaymidi -p 14 {}/mid/test.mid".format(self.data_dir)])


	def update_software(self):
		logging.info("UPDATE SOFTWARE")
		self.zyngui.show_info("UPDATE SOFTWARE")
		self.start_command([self.sys_dir + "/scripts/update_zynthian.sh"])


	def is_update_available(self):
		repos = ["/zynthian/zyncoder", "/zynthian/zynthian-ui", "/zynthian/zynthian-sys", "/zynthian/zynthian-webconf", "/zynthian/zynthian-data"]
		update_available = False
		for path in repos:
			update_available |= (check_output("git -C %s status --porcelain -bs | grep behind | wc -l" % path, shell=True).decode()[:1] == '1')
		return update_available


	def check_for_updates(self):
		self.zyngui.show_info("CHECK FOR UPDATES")
		self.start_command(["git -C /zynthian/zyncoder remote update; git -C /zynthian/zynthian-ui remote update; git -C /zynthian/zynthian-sys remote update; git -C /zynthian/zynthian-webconf remote update; git -C /zynthian/zynthian-data remote update"])


	def update_system(self):
		logging.info("UPDATE SYSTEM")
		self.zyngui.show_info("UPDATE SYSTEM")
		self.start_command([self.sys_dir + "/scripts/update_system.sh"])


	def restart_gui(self):
		logging.info("RESTART ZYNTHIAN-UI")
		self.last_state_action()
		self.zyngui.exit(102)


	def exit_to_console(self):
		logging.info("EXIT TO CONSOLE")
		self.last_state_action()
		self.zyngui.exit(101)


	def reboot(self):
		self.zyngui.show_confirm("Do you really want to reboot?", self.reboot_confirmed)


	def reboot_confirmed(self, params=None):
		logging.info("REBOOT")
		self.last_state_action()
		self.zyngui.exit(100)


	def power_off(self):
		self.zyngui.show_confirm("Do you really want to power off?", self.power_off_confirmed)


	def power_off_confirmed(self, params=None):
		logging.info("POWER OFF")
		self.last_state_action()
		self.zyngui.exit(0)


	def last_state_action(self):
		if zynthian_gui_config.restore_last_state:
			self.zyngui.screens['snapshot'].save_last_state_snapshot()
		else:
			self.zyngui.screens['snapshot'].delete_last_state_snapshot()


#------------------------------------------------------------------------------
