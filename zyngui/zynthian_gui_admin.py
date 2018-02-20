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
import sys
import signal
import logging
from time import sleep
from threading  import Thread
from subprocess import check_output, Popen, PIPE

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_selector

#------------------------------------------------------------------------------
# Configure logging
#------------------------------------------------------------------------------

# Set root logging level
logging.basicConfig(stream=sys.stderr, level=zynthian_gui_config.log_level)

#-------------------------------------------------------------------------------
# Zynthian Admin GUI Class
#-------------------------------------------------------------------------------
class zynthian_gui_admin(zynthian_gui_selector):

	def __init__(self):
		self.commands=None
		self.thread=None
		self.child_pid=None
		self.last_action=None
		super().__init__('Action', True)
    
	def fill_list(self):
		self.list_data=[]
		self.list_data.append((self.network_info,0,"Network Info"))
		if self.is_service_active("wpa_supplicant"):
			self.list_data.append((self.stop_wifi,0,"Stop WIFI"))
		else:
			self.list_data.append((self.start_wifi,0,"Start WIFI"))
		if os.environ.get('ZYNTHIAN_TOUCHOSC'):
			if self.is_service_active("touchosc2midi"):
				self.list_data.append((self.stop_touchosc2midi,0,"Stop TouchOSC"))
			else:
				self.list_data.append((self.start_touchosc2midi,0,"Start TouchOSC"))
		if self.is_process_running("jack_capture"):
			self.list_data.append((self.stop_recording,0,"Stop Audio Recording"))
		else:
			self.list_data.append((self.start_recording,0,"Start Audio Recording"))
		if os.environ.get('ZYNTHIAN_AUBIONOTES'):
			if self.is_service_active("aubionotes"):
				self.list_data.append((self.stop_aubionotes,0,"Stop Audio -> MIDI"))
			else:
				self.list_data.append((self.start_aubionotes,0,"Start Audio -> MIDI"))
		self.list_data.append((self.midi_profile,0,"MIDI Profile"))
		self.list_data.append((self.test_audio,0,"Test Audio"))
		self.list_data.append((self.test_midi,0,"Test MIDI"))
		self.list_data.append((self.update_software,0,"Update Software"))
		#self.list_data.append((self.update_library,0,"Update Zynthian Library"))
		#self.list_data.append((self.update_system,0,"Update Operating System"))
		self.list_data.append((self.restart_gui,0,"Restart UI"))
		#self.list_data.append((self.exit_to_console,0,"Exit to Console"))
		self.list_data.append((self.reboot,0,"Reboot"))
		self.list_data.append((self.power_off,0,"Power Off"))
		super().fill_list()

	def select_action(self, i):
		self.last_action=self.list_data[i][0]
		self.last_action()

	def set_select_path(self):
		self.select_path.set("Admin")

	def is_process_running(self, procname):
		cmd="ps -e | grep %s" % procname
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
			if len(result)>3: return True
			else: return False
		except Exception as e:
			return False

	def is_service_active(self, service):
		cmd="systemctl is-active %s" % service
		try:
			result=check_output(cmd, shell=True).decode('utf-8','ignore')
		except Exception as e:
			result="ERROR: %s" % e
		#print("Is service "+str(service)+" active? => "+str(result))
		if result.strip()=='active': return True
		else: return False

	def execute_commands(self):
		zynthian_gui_config.zyngui.start_loading()
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			zynthian_gui_config.zyngui.add_info("\nExecuting:\n%s" % cmd)
			try:
				result=check_output(cmd, shell=True).decode('utf-8','ignore')
			except Exception as e:
				result="ERROR: %s" % e
			logging.info(result)
			zynthian_gui_config.zyngui.add_info("\nResult:\n%s" % result)
		self.commands=None
		zynthian_gui_config.zyngui.hide_info_timer(5000)
		zynthian_gui_config.zyngui.stop_loading()
		self.fill_list()

	def start_command(self,cmds):
		if not self.commands:
			logging.info("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.execute_commands, args=())
			self.thread.daemon = True # thread dies with the program
			self.thread.start()

	def killable_execute_commands(self):
		#zynthian_gui_config.zyngui.start_loading()
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			zynthian_gui_config.zyngui.add_info("\nExecuting: %s" % cmd)
			try:
				proc=Popen(cmd.split(" "), stdout=PIPE, stderr=PIPE)
				self.child_pid=proc.pid
				zynthian_gui_config.zyngui.add_info("\nPID: %s" % self.child_pid)
				(output, error)=proc.communicate()
				self.child_pid=None
				if error:
					result="ERROR: %s" % error
				else:
					result=output
			except Exception as e:
				result="ERROR: %s" % e
			logging.info(result)
			zynthian_gui_config.zyngui.add_info("\n %s" % result)
		self.commands=None
		zynthian_gui_config.zyngui.hide_info_timer(5000)
		#zynthian_gui_config.zyngui.stop_loading()
		self.fill_list()

	def killable_start_command(self,cmds):
		if not self.commands:
			logging.info("Starting Command Sequence ...")
			self.commands=cmds
			self.thread=Thread(target=self.killable_execute_commands, args=())
			self.thread.daemon = True # thread dies with the program
			self.thread.start()

	def kill_command(self):
		if self.child_pid:
			logging.info("Killing process %s" % self.child_pid)
			os.kill(self.child_pid, signal.SIGTERM)
			self.child_pid=None
			if self.last_action==self.test_midi:
				check_output("systemctl stop a2jmidid", shell=True)
				zynthian_gui_config.zyngui.all_sounds_off()

	def update_software(self):
		logging.info("UPDATE SOFTWARE")
		zynthian_gui_config.zyngui.show_info("UPDATE SOFTWARE")
		self.start_command(["cd ./sys-scripts;./update_zynthian.sh"])

	def update_library(self):
		logging.info("UPDATE LIBRARY")
		zynthian_gui_config.zyngui.show_info("UPDATE LIBRARY")
		self.start_command(["cd ./sys-scripts;./update_zynthian_data.sh"])

	def update_system(self):
		logging.info("UPDATE SYSTEM")
		zynthian_gui_config.zyngui.show_info("UPDATE SYSTEM")
		self.start_command(["cd ./sys-scripts;./update_system.sh"])

	def network_info(self):
		logging.info("NETWORK INFO")
		zynthian_gui_config.zyngui.show_info("NETWORK INFO:")
		self.start_command(["hostname -I | cut -f1 -d' '"])

	def test_audio(self):
		logging.info("TESTING AUDIO")
		zynthian_gui_config.zyngui.show_info("TEST AUDIO")
		self.killable_start_command(["mpg123 ./data/audio/test.mp3"])

	def test_midi(self):
		logging.info("TESTING MIDI")
		zynthian_gui_config.zyngui.show_info("TEST MIDI")
		check_output("systemctl start a2jmidid", shell=True)
		self.killable_start_command(["aplaymidi -p 14 ./data/mid/test.mid"])

	def start_recording(self):
		logging.info("RECORDING STARTED...")
		try:
			cmd=os.environ.get('ZYNTHIAN_SYS_DIR')+"/sbin/jack_capture.sh --zui"
			#logging.info("COMMAND: %s" % cmd)
			rec_proc=Popen(cmd,shell=True,env=os.environ)
			sleep(0.5)
			check_output("echo play | jack_transport", shell=True)
		except Exception as e:
			logging.error("ERROR STARTING RECORDING: %s" % e)
			zynthian_gui_config.zyngui.show_info("ERROR STARTING RECORDING:\n %s" % e)
			zynthian_gui_config.zyngui.hide_info_timer(5000)
		self.fill_list()

	def stop_recording(self):
		logging.info("STOPPING RECORDING...")
		check_output("echo stop | jack_transport", shell=True)
		while self.is_process_running("jack_capture"):
			sleep(1)
		self.fill_list()

	def start_wifi(self):
		logging.info("STARTING WIFI")
		check_output("systemctl start wpa_supplicant", shell=True)
		check_output("ifup wlan0", shell=True)
		self.fill_list()

	def stop_wifi(self):
		logging.info("STOPPING WIFI")
		check_output("systemctl stop wpa_supplicant", shell=True)
		check_output("ifdown wlan0", shell=True)
		self.fill_list()

	def start_touchosc2midi(self):
		logging.info("STARTING touchosc2midi")
		check_output("systemctl start touchosc2midi", shell=True)
		self.fill_list()

	def stop_touchosc2midi(self):
		logging.info("STOPPING touchosc2midi")
		check_output("systemctl stop touchosc2midi", shell=True)
		self.fill_list()

	def start_aubionotes(self):
		logging.info("STARTING aubionotes")
		check_output("systemctl start aubionotes", shell=True)
		self.fill_list()

	def stop_aubionotes(self):
		logging.info("STOPPING aubionotes")
		check_output("systemctl stop aubionotes", shell=True)
		self.fill_list()

	def midi_profile(self):
		logging.info("MIDI PROFILE")
		zynthian_gui_config.zyngui.show_modal("midi_profile")

	def restart_gui(self):
		logging.info("RESTART GUI")
		zynthian_gui_config.zyngui.exit(102)

	def exit_to_console(self):
		logging.info("EXIT TO CONSOLE")
		zynthian_gui_config.zyngui.exit(101)

	def reboot(self):
		logging.info("REBOOT")
		zynthian_gui_config.zyngui.exit(100)

	def power_off(self):
		logging.info("POWER OFF")
		zynthian_gui_config.zyngui.exit(0)

#------------------------------------------------------------------------------
