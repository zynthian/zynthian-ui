# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Config Library
# 
# Zynthian Config library and tools
# 
# Copyright (C) 2015-2017 Fernando Moyano <jofemodo@zynthian.org>
#
#********************************************************************
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
#********************************************************************

import os
import re
import sys
import logging
from shutil import copyfile
from subprocess import check_output

#-------------------------------------------------------------------------------
# Configure logging
#-------------------------------------------------------------------------------

logger=logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

#-------------------------------------------------------------------------------
# Config related functions
#-------------------------------------------------------------------------------

def get_config_fpath():
	fpath=os.environ.get('ZYNTHIAN_CONFIG_DIR','/zynthian/zynthian-sys/scripts')+"/zynthian_envars.sh"
	if not os.path.isfile(fpath):
		fpath=os.environ.get('ZYNTHIAN_SYS_DIR')+"/scripts/zynthian_envars.sh"
	elif not os.path.isfile(fpath):
		fpath="./zynthian_envars.sh"
	return fpath


def get_midi_config_fpath(fpath=None):
	if not fpath:
		fpath=os.environ.get("ZYNTHIAN_SCRIPT_MIDI_PROFILE",
			os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/midi-profiles/default.sh")
	if not os.path.isfile(fpath):
		#Try to copy from default template
		default_src= "%s/config/default_midi_profile.sh" % os.getenv('ZYNTHIAN_SYS_DIR',"/zynthian/zynthian-sys")
		copyfile(default_src, fpath)

	return fpath


def load_config(set_env=True, fpath=None):
	if not fpath:
		fpath=get_config_fpath()

	# Get config file content
	with open(fpath) as f:
		lines = f.readlines()

	# Load config varnames
	varnames=[]
	pattern=re.compile("^export ([^\s]*?)=")
	for line in lines:
		res=pattern.match(line)
		if res:
			varnames.append(res.group(1))
			#logging.debug("CONFIG VARNAME: %s" % res.group(1))

	# Execute config script and dump environment
	env=check_output("source %s;env" % fpath, shell=True, universal_newlines=True, executable="/bin/bash")

	# Parse environment dump
	config={}
	pattern=re.compile("^([^\=]*)=(.*)$")
	lines=env.split("\n")
	for line in lines:
		res=pattern.match(line)
		if res:
			vn=res.group(1)
			if vn in varnames:
				val=res.group(2)
				config[vn]=val
				logging.debug("CONFIG VAR: %s=%s" % (vn,val))
				# Set local environment
				if set_env:
					os.environ[vn]=val

	return config


def load_midi_config(set_env=True, fpath=None):
	return load_config(set_env, get_midi_config_fpath(fpath))


def save_config(config, update_sys=False):
	fpath=get_config_fpath()

	# Get config file content
	with open(fpath) as f:
		lines = f.readlines()

	# Find and replace lines to update
	updated=[]
	add_row=1
	pattern=re.compile("^export ([^\s]*?)=")
	for i,line in enumerate(lines):
		res=pattern.match(line)
		if res:
			varname=res.group(1)
			if varname in config:
				value=config[varname].replace("\n", "\\n")
				value=value.replace("\r", "")
				os.environ[varname]=value
				lines[i]="export %s=\"%s\"\n" % (varname,value)
				updated.append(varname)
				logging.info(lines[i])
		if line[0:17]=="# Directory Paths":
			add_row=i-1

	# Add the rest
	vars_to_add=set(config.keys())-set(updated)
	for varname in vars_to_add:
		value=config[varname].replace("\n", "\\n")
		value=value.replace("\r", "")
		os.environ[varname]=value
		lines.insert(add_row,"export %s=\"%s\"\n" % (varname,value))
		logging.info(lines[add_row])

	# Write updated config file
	with open(fpath,'w') as f:
		f.writelines(lines)
		f.flush()
		os.fsync(f.fileno())

	# Update System Configuration
	if update_sys:
		try:
			check_output(os.environ.get('ZYNTHIAN_SYS_DIR')+"/scripts/update_zynthian_sys.sh", shell=True)
		except Exception as e:
			logging.error("Updating Sytem Config: %s" % e)


#-------------------------------------------------------------------------------
# MIDI Config related functions
#-------------------------------------------------------------------------------


def get_disabled_midi_in_ports(midi_ports):
	#Parse DISABLED_IN ports
	disabled_in_re = re.compile("^DISABLED_IN=(.*)$",re.MULTILINE)
	m=disabled_in_re.search(midi_ports)
	if m:
		disabled_midi_in_ports=m.group(1).split(",")
		logging.debug("DISABLED_MIDI_IN = %s" % disabled_midi_in_ports)
	else:
		disabled_midi_in_ports=""
		logging.warning("Using default DISABLED MIDI IN ports")
	return disabled_midi_in_ports


def get_enabled_midi_out_ports(midi_ports):
	#Parse ENABLED_OUT ports
	enabled_out_re = re.compile("^ENABLED_OUT=(.*)$",re.MULTILINE)
	m=enabled_out_re.search(midi_ports)
	if m:
		enabled_midi_out_ports=m.group(1).split(",")
		logging.debug("ENABLED_MIDI_OUT = %s" % enabled_midi_out_ports)
	else:
		enabled_midi_out_ports=["ttymidi:MIDI_out"]
		logging.warning("Using default ENABLED MIDI OUT ports")
	return enabled_midi_out_ports


#------------------------------------------------------------------------------
