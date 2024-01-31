#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Admin Class
# 
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

import os
import re
import signal
import logging
from time import sleep
from threading import Thread
from curses import A_HORIZONTAL
from subprocess import check_output, Popen, PIPE, STDOUT

# Zynthian specific modules
import zynconf
import zynautoconnect
from zyncoder.zyncore import lib_zyncore
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# -------------------------------------------------------------------------------
# Zynthian Admin GUI Class
# -------------------------------------------------------------------------------


class zynthian_gui_admin(zynthian_gui_selector):

	data_dir = os.environ.get('ZYNTHIAN_DATA_DIR', "/zynthian/zynthian-data")
	sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR', "/zynthian/zynthian-sys")

	def __init__(self):
		self.commands = None
		self.thread = None
		self.child_pid = None
		self.last_action = None
		self.update_available = False

		super().__init__('Action', True)

		self.state_manager = self.zyngui.state_manager

		if self.state_manager.allow_rbpi_headphones():
			self.default_rbpi_headphones()


	def refresh_status(self):
		super().refresh_status()
		if self.update_available != self.state_manager.update_available:
			self.update_available = self.state_manager.update_available
			self.fill_list()


	def build_view(self):
		self.state_manager.check_for_updates()
		return super().build_view()


	def fill_list(self):
		self.list_data = []
		self.list_data.append((None, 0, "> MIDI"))

		self.list_data.append((self.zyngui.midi_in_config, 0, "MIDI Input Devices"))
		self.list_data.append((self.zyngui.midi_out_config, 0, "MIDI Output Devices"))
		#self.list_data.append((self.midi_profile, 0, "MIDI Profile"))

		if zynthian_gui_config.midi_prog_change_zs3:
			self.list_data.append((self.toggle_prog_change_zs3, 0, "\u2612 Program Change for ZS3"))
		else:
			self.list_data.append((self.toggle_prog_change_zs3, 0, "\u2610 Program Change for ZS3"))
			if zynthian_gui_config.midi_bank_change:
				self.list_data.append((self.toggle_bank_change, 0, "\u2612 MIDI Bank Change"))
			else:
				self.list_data.append((self.toggle_bank_change, 0, "\u2610 MIDI Bank Change"))

		if zynthian_gui_config.preset_preload_noteon:
			self.list_data.append((self.toggle_preset_preload_noteon, 0, "\u2612 Note-On Preset Preload"))
		else:
			self.list_data.append((self.toggle_preset_preload_noteon, 0, "\u2610 Note-On Preset Preload"))

		if zynthian_gui_config.transport_clock_source == 0:
			if zynthian_gui_config.midi_sys_enabled:
				self.list_data.append((self.toggle_midi_sys, 0, "\u2612 MIDI System Messages"))
			else:
				self.list_data.append((self.toggle_midi_sys, 0, "\u2610 MIDI System Messages"))

		self.list_data.append((None, 0, "> AUDIO"))

		if self.state_manager.allow_rbpi_headphones():
			if zynthian_gui_config.rbpi_headphones:
				self.list_data.append((self.stop_rbpi_headphones, 0, "\u2612 RBPi Headphones"))
			else:
				self.list_data.append((self.start_rbpi_headphones, 0, "\u2610 RBPi Headphones"))

		if zynthian_gui_config.snapshot_mixer_settings:
			self.list_data.append((self.toggle_snapshot_mixer_settings, 0, "\u2612 Audio Levels on Snapshots"))
		else:
			self.list_data.append((self.toggle_snapshot_mixer_settings, 0, "\u2610 Audio Levels on Snapshots"))

		if zynthian_gui_config.enable_dpm:
			self.list_data.append((self.toggle_dpm, 0, "\u2612 Mixer Peak Meters"))
		else:
			self.list_data.append((self.toggle_dpm, 0, "\u2610 Mixer Peak Meters"))

		self.list_data.append((None, 0, "> NETWORK"))

		self.list_data.append((self.network_info, 0, "Network Info"))

		if zynconf.is_wifi_active():
			if zynconf.is_service_active("hostapd"):
				self.list_data.append((self.state_manager.stop_wifi, 0, "\u2612 Wi-Fi Hotspot"))
			else:
				self.list_data.append((self.state_manager.stop_wifi, 0, "\u2612 Wi-Fi"))
		else:
			self.list_data.append((self.state_manager.start_wifi, 0, "\u2610 Wi-Fi"))
			self.list_data.append((self.state_manager.start_wifi_hotspot, 0, "\u2610 Wi-Fi Hotspot"))

		if zynconf.is_service_active("vncserver0"):
			self.list_data.append((self.state_manager.stop_vncserver, 0, "\u2612 VNC Server"))
		else:
			self.list_data.append((self.state_manager.start_vncserver, 0, "\u2610 VNC Server"))

		self.list_data.append((None, 0, "> SETTINGS"))
		if self.zyngui.screens["brightness_config"].get_num_zctrls() > 0:
			self.list_data.append((self.zyngui.brightness_config, 0, "Brightness"))
		if "cv_config" in self.zyngui.screens:
			self.list_data.append((self.show_cv_config, 0, "CV Settings"))
		self.list_data.append((self.zyngui.calibrate_touchscreen, 0, "Calibrate Touchscreen"))

		self.list_data.append((None, 0, "> TEST"))
		self.list_data.append((self.test_audio, 0, "Test Audio"))
		self.list_data.append((self.test_midi, 0, "Test MIDI"))

		self.list_data.append((None, 0, "> SYSTEM"))
		if self.zyngui.capture_log_fname:
			self.list_data.append((self.workflow_capture_stop, 0, "\u2612 Capture Workflow"))
		else:
			self.list_data.append((self.workflow_capture_start, 0, "\u2610 Capture Workflow"))
		if self.state_manager.update_available:
			self.list_data.append((self.update_software, 0, "Update Software"))
		#self.list_data.append((self.update_system, 0, "Update Operating System"))
		#self.list_data.append((None, 0, "> POWER"))
		#self.list_data.append((self.restart_gui, 0, "Restart UI"))
		if zynthian_gui_config.debug_thread:
			self.list_data.append((self.exit_to_console, 0, "Exit"))
		self.list_data.append((self.reboot, 0, "Reboot"))
		self.list_data.append((self.power_off, 0, "Power Off"))
		super().fill_list()

	def select_action(self, i, t='S'):
		if self.list_data[i][0]:
			self.last_action = self.list_data[i][0]
			self.last_action()

	def set_select_path(self):
		self.select_path.set("Admin")

	def execute_commands(self):
		self.state_manager.start_busy("admin_commands")
		error_counter = 0
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			self.zyngui.add_info("EXECUTING:\n", "EMPHASIS")
			self.zyngui.add_info("{}\n".format(cmd))
			try:
				self.proc = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
				self.zyngui.add_info("RESULT:\n", "EMPHASIS")
				for line in self.proc.stdout:
					if re.search("ERROR", line, re.IGNORECASE):
						error_counter += 1
						tag = "ERROR"
					elif re.search("Already", line, re.IGNORECASE):
						tag = "SUCCESS"
					else:
						tag = None
					logging.info(line.rstrip())
					self.zyngui.add_info(line, tag)
				self.zyngui.add_info("\n")
			except Exception as e:
				logging.error(e)
				self.zyngui.add_info("ERROR: %s\n" % e, "ERROR")

		if error_counter > 0:
			logging.info("COMPLETED WITH {} ERRORS!".format(error_counter))
			self.zyngui.add_info("COMPLETED WITH {} ERRORS!".format(error_counter), "WARNING")
		else:
			logging.info("COMPLETED OK!")
			self.zyngui.add_info("COMPLETED OK!", "SUCCESS")

		self.commands = None
		self.zyngui.add_info("\n\n")
		self.zyngui.hide_info_timer(5000)
		self.state_manager.end_busy("admin_commands")

	def start_command(self, cmds):
		if not self.commands:
			logging.info("Starting Command Sequence")
			self.commands = cmds
			self.thread = Thread(target=self.execute_commands, args=())
			self.thread.name = "command sequence"
			self.thread.daemon = True  # thread dies with the program
			self.thread.start()

	def killable_execute_commands(self):
		#self.state_manager.start_busy("admin commands")
		for cmd in self.commands:
			logging.info("Executing Command: %s" % cmd)
			self.zyngui.add_info("EXECUTING:\n", "EMPHASIS")
			self.zyngui.add_info("{}\n".format(cmd))
			try:
				proc = Popen(cmd.split(" "), stdout=PIPE, stderr=PIPE)
				self.child_pid = proc.pid
				self.zyngui.add_info("\nPID: %s" % self.child_pid)
				(output, error) = proc.communicate()
				self.child_pid = None
				if error:
					result = "ERROR: %s" % error
					logging.error(result)
					self.zyngui.add_info(result, "ERROR")
				if output:
					logging.info(output)
					self.zyngui.add_info(output)
			except Exception as e:
				result = "ERROR: %s" % e
				logging.error(result)
				self.zyngui.add_info(result, "ERROR")

		self.commands = None
		self.zyngui.hide_info_timer(5000)
		#self.state_manager.end_busy("admin commands")

	def killable_start_command(self, cmds):
		if not self.commands:
			logging.info("Starting Command Sequence")
			self.commands = cmds
			self.thread = Thread(target=self.killable_execute_commands, args=())
			self.thread.name = "killable command sequence"
			self.thread.daemon = True  # thread dies with the program
			self.thread.start()

	def kill_command(self):
		if self.child_pid:
			logging.info("Killing process %s" % self.child_pid)
			os.kill(self.child_pid, signal.SIGTERM)
			self.child_pid = None
			if self.last_action == self.test_midi:
				self.state_manager.all_sounds_off()

	# ------------------------------------------------------------------------------
	# CONFIG OPTIONS
	# ------------------------------------------------------------------------------

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
			zynautoconnect.request_audio_connect()

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

	# Start/Stop RBPI Headphones depending on configuration
	def default_rbpi_headphones(self):
		if zynthian_gui_config.rbpi_headphones:
			self.start_rbpi_headphones(False)
		else:
			self.stop_rbpi_headphones(False)

	def toggle_dpm(self):
		zynthian_gui_config.enable_dpm = not zynthian_gui_config.enable_dpm
		self.fill_list()

	def toggle_snapshot_mixer_settings(self):
		if zynthian_gui_config.snapshot_mixer_settings:
			logging.info("Mixer Settings on Snapshots OFF")
			zynthian_gui_config.snapshot_mixer_settings = False
		else:
			logging.info("Mixer Settings on Snapshots ON")
			zynthian_gui_config.snapshot_mixer_settings = True

		# Update Config
		zynconf.save_config({ 
			"ZYNTHIAN_UI_SNAPSHOT_MIXER_SETTINGS": str(int(zynthian_gui_config.snapshot_mixer_settings))
		})
		self.fill_list()

	def toggle_midi_sys(self):
		if zynthian_gui_config.midi_sys_enabled:
			logging.info("MIDI System Messages OFF")
			zynthian_gui_config.midi_sys_enabled = False
		else:
			logging.info("MIDI System Messages ON")
			zynthian_gui_config.midi_sys_enabled = True

		# Update MIDI profile
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_SYS_ENABLED": str(int(zynthian_gui_config.midi_sys_enabled))
		})

		lib_zyncore.set_midi_filter_system_events(zynthian_gui_config.midi_sys_enabled)
		self.fill_list()

	def toggle_prog_change_zs3(self):
		if zynthian_gui_config.midi_prog_change_zs3:
			logging.info("ZS3 Program Change OFF")
			zynthian_gui_config.midi_prog_change_zs3 = False
		else:
			logging.info("ZS3 Program Change ON")
			zynthian_gui_config.midi_prog_change_zs3 = True

		# Save config
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_PROG_CHANGE_ZS3": str(int(zynthian_gui_config.midi_prog_change_zs3))
		})

		self.fill_list()

	def toggle_bank_change(self):
		if zynthian_gui_config.midi_bank_change:
			logging.info("MIDI Bank Change OFF")
			zynthian_gui_config.midi_bank_change = False
		else:
			logging.info("MIDI Bank Change ON")
			zynthian_gui_config.midi_bank_change = True

		# Save config
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_BANK_CHANGE": str(int(zynthian_gui_config.midi_bank_change))
		})

		self.fill_list()

	def toggle_preset_preload_noteon(self):
		if zynthian_gui_config.preset_preload_noteon:
			logging.info("Preset Preload OFF")
			zynthian_gui_config.preset_preload_noteon = False
		else:
			logging.info("Preset Preload ON")
			zynthian_gui_config.preset_preload_noteon = True

		# Save config
		zynconf.update_midi_profile({ 
			"ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON": str(int(zynthian_gui_config.preset_preload_noteon))
		})
		self.fill_list()

	def show_cv_config(self):
		self.zyngui.show_screen("cv_config")

	def midi_profile(self):
		logging.info("MIDI Profile")
		self.zyngui.show_screen("midi_profile")

	# ------------------------------------------------------------------------------
	# NETWORK INFO
	# ------------------------------------------------------------------------------

	def network_info(self):
		self.zyngui.show_info("NETWORK INFO\n")

		res = zynconf.network_info()
		for k, v in res.items():
			self.zyngui.add_info(" {} => {}\n".format(k, v[0]), v[1])

		self.zyngui.hide_info_timer(5000)
		self.zyngui.state_manager.end_busy("gui_admin")

	# ------------------------------------------------------------------------------
	# TEST FUNCTIONS
	# ------------------------------------------------------------------------------

	def test_audio(self):
		logging.info("TESTING AUDIO")
		self.zyngui.show_info("TEST AUDIO")
		#self.killable_start_command(["mpg123 {}/audio/test.mp3".format(self.data_dir)])
		self.killable_start_command(["mplayer -nogui -noconsolecontrols -nolirc -nojoystick -really-quiet -ao jack {}/audio/test.mp3".format(self.data_dir)])
		zynautoconnect.request_audio_connect()

	def test_midi(self):
		logging.info("TESTING MIDI")
		self.zyngui.show_info("TEST MIDI")
		self.killable_start_command(["aplaymidi -p 14 {}/mid/test.mid".format(self.data_dir)])

		if self.zyngui.capture_log_fname:
			self.list_data.append((self.workflow_capture_stop, 0, "\u2612 Workflow Capture"))
		else:
			self.list_data.append((self.workflow_capture_start, 0, "\u2610 Workflow Capture"))

	# ------------------------------------------------------------------------------
	# SYSTEM FUNCTIONS
	# ------------------------------------------------------------------------------

	def debug(self):
		breakpoint()

	def workflow_capture_start(self):
		self.zyngui.start_capture_log()
		self.zyngui.close_screen()

	def workflow_capture_stop(self):
		self.zyngui.stop_capture_log()
		self.fill_list()

	def update_software(self):
		logging.info("UPDATE SOFTWARE")
		self.last_state_action()
		self.zyngui.show_info("UPDATE SOFTWARE")
		self.start_command([self.sys_dir + "/scripts/update_zynthian.sh"])
		self.state_manager.update_available = False

	def update_system(self):
		logging.info("UPDATE SYSTEM")
		self.last_state_action()
		self.zyngui.show_info("UPDATE SYSTEM")
		self.start_command([self.sys_dir + "/scripts/update_system.sh"])

	def restart_gui(self):
		logging.info("RESTART ZYNTHIAN-UI")
		self.zyngui.show_splash("Restarting UI")
		self.last_state_action()
		self.zyngui.exit(102)

	def exit_to_console(self):
		logging.info("EXIT TO CONSOLE")
		self.zyngui.show_splash("Exiting")
		self.last_state_action()
		self.zyngui.exit(101)

	def reboot(self):
		self.zyngui.show_confirm("Do you really want to reboot?", self.reboot_confirmed)

	def reboot_confirmed(self, params=None):
		logging.info("REBOOT")
		self.zyngui.show_splash("Rebooting")
		self.last_state_action()
		self.zyngui.exit(100)

	def power_off(self):
		self.zyngui.show_confirm("Do you really want to power off?", self.power_off_confirmed)

	def power_off_confirmed(self, params=None):
		logging.info("POWER OFF")
		self.zyngui.show_splash("Powering Off")
		self.last_state_action()
		self.zyngui.exit(0)

	def last_state_action(self):
		if zynthian_gui_config.restore_last_state:
			self.state_manager.save_last_state_snapshot()
		else:
			self.state_manager.delete_last_state_snapshot()

# ------------------------------------------------------------------------------
