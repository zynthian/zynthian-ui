#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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
import logging
import importlib
from pathlib import Path
from os.path import isfile, join

# Zynthian specific modules
import zynautoconnect
from zyngui import zynthian_gui_config
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

#------------------------------------------------------------------------------
# Zynthian Control Device Manager Class
#------------------------------------------------------------------------------

class zynthian_ctrldev_manager():

	ctrldev_dpath = os.environ.get('ZYNTHIAN_UI_DIR', "/zynthian/zynthian-ui") + "/zyngui/ctrldev"

	# Function to initialise class
	def __init__(self):
		self.zyngui = zynthian_gui_config.zyngui

		self.drivers = {}
		self.load_drivers()
		self.zynpad_drivers = self.get_zynpad_drivers()
		self.zynmixer_drivers = self.get_zynmixer_drivers()

		self.ctrldevs = [None for idev in range(17)]


	def load_drivers(self):
		for f in sorted(os.listdir(self.ctrldev_dpath)):
			module_path = join(self.ctrldev_dpath, f)
			if not f.startswith('.') and isfile(module_path) and f[-3:].lower() == '.py':
				module_name = Path(module_path).stem
				if module_name.startswith("zynthian_ctrldev_"):
					#ctrldev_name = module_name[len("zynthian_ctrldev_"):]
					try:
						spec = importlib.util.spec_from_file_location(module_name, module_path)
						module = importlib.util.module_from_spec(spec)
						spec.loader.exec_module(module)
						class_ = getattr(module, module_name)
						ctrldev_id = class_.dev_id
						if ctrldev_id not in self.drivers:
							self.drivers[ctrldev_id] = class_()
							logging.info("Loaded ctrldev driver {}.".format(module_name))
					except Exception as e:
						logging.error("Can't load ctrldev driver {} => {}".format(module_name, e))


	def reload_drivers(self):
		self.drivers = {}
		self.load_drivers()


	def get_zynpad_drivers(self):
		res = {}
		for id, driver in self.drivers.items():
			if driver.dev_zynpad:
				res[id] = driver
		return res


	def get_zynmixer_drivers(self):
		res = {}
		for id, driver in self.drivers.items():
			if driver.dev_zynmixer:
				res[id] = driver
		return res


	def init_device(self, idev):
		dev_id = zynautoconnect.get_midi_device_name(idev)
		# If a driver that matches the device ID string is found ...
		if dev_id and dev_id in self.drivers:
			driver = self.drivers[dev_id]
			driver.setup(idev)
			self.ctrldevs[idev] = driver
			return driver


	def end_device(self, idev):
		if idev > 0 and idev <= 16 and self.ctrldevs[idev]:
			self.ctrldevs[idev].release()
			self.ctrldevs[idev] = None


	def refresh_device(self, idev, force=False):
		if idev > 0 and idev <= 16 and self.ctrldevs[idev]:
			self.ctrldevs[idev].refresh(force)


	def init_device_by_id(self, dev_id):
		# Find index in connected devices
		try:
			idev = zynautoconnect.devices_in.index(dev_id) + 1
		except:
			return None

		# If found an available driver...
		if dev_id in self.drivers:
			driver = self.drivers[dev_id]
			driver.setup(idev)
			self.ctrldevs[idev] = driver
			return driver


	def init_all(self):
		for idev in range(1, 16):
			self.init_device(idev)


	def end_all(self):
		for idev in range(1, 16):
			self.end_device(idev)


	def refresh_all(self, force=False):
		for idev in range(1, 16):
			if self.ctrldevs[idev]:
				self.ctrldevs[idev].refresh(force)


	def sleep_on(self):
		for idev in range(1, 16):
			if self.ctrldevs[idev]:
				self.ctrldevs[idev].sleep_on()


	def sleep_off(self):
		for idev in range(1, 16):
			if self.ctrldevs[idev]:
				self.ctrldevs[idev].sleep_off()


	def zynpad_ctrldev_autoconfig(self):
		zynpad = self.zyngui.screens['zynpad']
		if not zynpad.ctrldev_idev and zynpad.ctrldev_id:
			try:
				if zynpad.ctrldev_id in self.zynpad_drivers.keys():
					driver = self.init_device_by_id(zynpad.ctrldev_id)
					if driver:
						zynpad.ctrldev = driver
						zynpad.ctrldev_idev = driver.idev
			except Exception as err:
				# logging.debug(err)
				pass
		if not zynpad.ctrldev_idev:
			try:
				for dev_id in self.zynpad_drivers.keys():
					driver = self.init_device_by_id(dev_id)
					if driver:
						zynpad.ctrldev = driver
						zynpad.ctrldev_id = dev_id
						zynpad.ctrldev_idev = driver.idev
						break
			except Exception as err:
				# logging.debug(err)
				pass
		return zynpad.ctrldev_idev


	def zynmixer_ctrldev_autoconfig(self):
		zynmixer = self.zyngui.screens['audio_mixer']
		if not zynmixer.ctrldev_idev and zynmixer.ctrldev_id:
			try:
				if zynmixer.ctrldev_id in self.zynmixer_drivers.keys():
					driver = self.init_device_by_id(zynmixer.ctrldev_id)
					if driver:
						zynmixer.ctrldev = driver
						zynmixer.ctrldev_idev = driver.idev
			except Exception as err:
				# logging.debug(err)
				pass
		if not zynmixer.ctrldev_idev:
			try:
				for dev_id in self.zynmixer_drivers.keys():
					driver = self.init_device_by_id(dev_id)
					if driver:
						zynmixer.ctrldev = driver
						zynmixer.ctrldev_id = dev_id
						zynmixer.ctrldev_idev = driver.idev
						break
			except Exception as err:
				# logging.debug(err)
				pass
		return zynmixer.ctrldev_idev


	def refresh_device_list(self):
		# Remove disconnected devices
		logging.debug("Refreshing control device list...")
		for idev in range(1, 16):
			dev_id = zynautoconnect.devices_in[idev - 1]
			if not dev_id:
				# If zynmixer device got disconnected ...
				if self.zyngui.screens['audio_mixer'].ctrldev_idev == idev:
					#logging.debug("Releasing mixer control device...")
					self.zyngui.screens['audio_mixer'].ctrldev_idev = 0
				# If zynpad device got disconnected ...
				if self.zyngui.screens['zynpad'].ctrldev_idev == idev:
					#logging.debug("Releasing zynpad control device...")
					self.zyngui.screens['zynpad'].ctrldev_idev = 0
					self.zyngui.screens['zynpad'].ctrldev = None
				# Release device if it's active
				if self.ctrldevs[idev]:
					self.end_device(idev)

		# Autoconfig devices
		self.zynmixer_ctrldev_autoconfig()
		self.zynpad_ctrldev_autoconfig()


	def midi_event(self, ev):
		idev = ((ev & 0xFF000000) >> 24)

		if idev > 0 and idev <= 16:
			#if idev>0 and idev<=len(zynautoconnect.devices_in):
			#	logging.debug("MIDI EVENT FROM '{}'".format(zynautoconnect.devices_in[idev - 1]))

			# Try device driver ...
			if self.ctrldevs[idev]:
				return self.ctrldevs[idev].midi_event(ev)

			# else, try zynpad
			elif idev == self.zyngui.screens['zynpad'].ctrldev_idev:
				return self.zyngui.screens['zynpad'].midi_event(ev)

		return False


#------------------------------------------------------------------------------------------------------------------
# Control device base class
#------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_base():

	dev_id = None  		# String that identifies the device (class variable!)
	dev_zynpad = False		# Can act as a zynpad trigger device
	dev_zynmixer = False	# Can act as an audio mixer controller device
	dev_pated = False	# Can act as a pattern editor device


	# Function to initialise class
	def __init__(self):
		self.idev = 0		# Slot index where the device is connected, starting from 1 (0 = None)
		self.zyngui = zynthian_gui_config.zyngui


	# Setup the device connected in slot #idev
	# Before calling this, the caller (ctrldev-manager) should check that driver's ID string matches device's ID string
	def setup(self, idev=None):
		if idev != self.idev:
			# Release currently selected device, if any ...
			self.release()
			# Init new selected device
			if idev > 0:
				self.idev = idev
				logging.info("Setting-up {} in slot {}".format(self.dev_id, self.idev))
				# Setup routing
				lib_zyncore.zmip_set_route_extdev(self.idev - 1, 0)
				zynautoconnect.midi_autoconnect(True)
				# Initialize new selected device
				self.init()
				self.refresh(force=True)


	def release(self):
		if self.idev > 0:
			logging.info("Releasing {} in slot {}".format(self.dev_id, self.idev))
			# If device is still connected, call end
			dev_id = zynautoconnect.get_midi_device_name(self.idev)
			if dev_id and dev_id == self.dev_id:
				self.end()
			# Restore routing
			lib_zyncore.zmip_set_route_extdev(self.idev - 1, 1)
			zynautoconnect.midi_autoconnect(True)
		self.idev = 0


	# Refresh device status (LED feedback, etc)
	# It *SHOULD* be implemented by child class
	def refresh(self, force=False):
		logging.debug("Refresh LEDs for {}: NOT IMPLEMENTED!".format(self.dev_id))


	# Device MIDI event handler
	# It *SHOULD* be implemented by child class
	def midi_event(self, ev):
		logging.debug("MIDI EVENT FROM '{}'".format(self.dev_id))


	# Light-Off LEDs
	# It *SHOULD* be implemented by child class
	def light_off(self):
		logging.debug("Lighting Off LEDs for {}: NOT IMPLEMENTED!".format(self.dev_id))


	# Sleep On
	# It *COULD* be improved by child class
	def sleep_on(self):
		self.light_off()


	# Sleep On
	# It *COULD* be improved by child class
	def sleep_off(self):
		self.refresh(True)


# ------------------------------------------------------------------------------------------------------------------
# Zynpad control device base class
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_zynpad(zynthian_ctrldev_base):

	dev_zynpad = True		# Can act as a zynpad trigger device


	def __init__(self):
		super().__init__()
		self.zynpad = self.zyngui.screens["zynpad"]


	def refresh(self, force=False):
		# When zynpad is shown, this is done by refresh_status, so no need to refresh twice
		if force or not self.zynpad.shown:
			self.refresh_pads(force)
			self.refresh_zynpad_bank()
		if force:
			self.refresh_zynpad_bank()


	# It *SHOULD* be implemented by child class
	def refresh_zynpad_bank(self):
		pass


	def refresh_pads(self, force=False):
		if force:
			self.light_off()
		for pad in range(self.zyngui.zynseq.col_in_bank ** 2):
			# It MUST be called for cleaning the dirty bit
			changed_state = self.zyngui.zynseq.libseq.hasSequenceChanged(self.zynpad.bank, pad)
			if changed_state or force:
				mode = self.zyngui.zynseq.libseq.getPlayMode(self.zynpad.bank, pad)
				state = self.zynpad.get_pad_state(pad)
				self.update_pad(pad, state, mode)


	def refresh_pad(self, pad, force=False):
		# It MUST be called for cleaning the dirty bit!!
		changed_state = self.zyngui.zynseq.libseq.hasSequenceChanged(self.zynpad.bank, pad)
		if changed_state or force:
			mode = self.zyngui.zynseq.libseq.getPlayMode(self.zynpad.bank, pad)
			state = self.zynpad.get_pad_state(pad)
			self.update_pad(pad, state, mode)


	# It *SHOULD* be implemented by child class
	def update_pad(self, pad, state, mode):
		pass
#------------------------------------------------------------------------------
