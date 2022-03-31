#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian Graph Manager
# 
# Copyright (C) 2015-2021 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2021-2021 Brian Walton <riban@zynthian.org>
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
#
# The purpose of this module is to manage the audio and MIDI processing modules
# that are loaded in Zynthian and the routing of interconnects between these
# modules and to physical interfaces. It manages the graph (nodes and
# interconnects) and the configuration of each engine (synth, audio plugin,
# etc.). The state of the graph can be saved as a snapshot.
#
# Node: Graph node, either JACK port or LV2 control port. May be identified by Engine:port
# Link: Interconnect between nodes
# Engine: Module processing audio/MIDI/control signals which contains nodes, e.g. LV2 plugin, synth engine, etc.
#

import os
import sys
import copy
import base64
import logging
import collections
from collections import OrderedDict
from json import JSONEncoder, JSONDecoder

# Zynthian specific modules
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Graph Manager Class
#------------------------------------------------------------------------------

class zynthian_graph_manager():

	# Function to initialise instance of class
	def __init__(self):
		self.engines = [] # List of engines in graph, each derived from zynthian_engine
		self.links = [] # List of interconnects (src_port, dst_port) Is this required or can be deduced by JACK graph?
		#	Links describe one or more JACK routes. They may be mono or multichannel audio or MIDI.
		#	Each engine object is derived zynthian_engine which defines its input and output ports, grouping individual i/o as appropriate to allow automatic connection and rule-based routing decisions, e.g. a mono output connecting to a stereo input will send mono to both
		# Links can be uniquely identified by the source and destination ports. This can be represented within a session with port UUIDs and within snapshot by list of destination ports each source port is connected to.


	# Function to add an engine to the graph
	# engine: Engine object to insert
	# source: Engine object immediately before insert point. (Optional - None to auto connect to physical input)
	# destination: Engine object immediately after insert point. (Optional - None to auto connect to new mixer input)
	def add_engine(self, engine, source=None, destination=None):
		pass


	# Function to remove an engine from the graph
	# engine: Object to remove
	# Note: This destroys the engine object
	def remove_engine(self, engine):
		pass


	# Function to move an engine within the graph
	# engine: Object to move
	# link: Interconnect to insert engine
	# Returns: True on success otherwise engine is not moved
	# Note: If no more engines exist in original chain and no input node is routed then chain is destroyed
	# Note: All existing connections to engine are removed and default connections are made in new position
	def move_engine(self, engine, link):
		pass


	# Function to remove chain from graph
	# chain: Index of chain to remove
	# Note: This destroys all engines in the chain
	def remove_chain(self, index):
		pass


	# Function to remove all chains from graph
	# Note: This destroys all engines in all chains
	def reset(self, index):
		pass


	# Function to get list of chains
	def get_chains(self):
		return []


	# Function to get list of engines in a chain
	# chain: id of chain to query
	def get_engines(self, chain):
		return []


	# Function to get list of inputs to an engine
	# engine: Object whose inputs are being queried
	# Returns: List of inputs
	def get_engine_inputs(self, engine):
		return []


	# Function to get list of outputs from an engine
	# engine: Object whose outputs are being queried
	# Returns: List of outputs
	def get_engine_outputs(self, engine):
		return []


	# Function to get list of interconnects to an input node
	# node: Input node being queried
	def get_input_links(self, node):
		return []


	# Function to get list of interconnects from an output node
	# node: node whose output is being queried
	def get_output_links(self, node):
		return []


	# Function to connect an engine's default audio outputs to an engine's default audio inputs
	# source: Source engine object
	# destination: Destination engine object
	def connect(self, source, destination):
		pass
	

	# Function to save graph as a snapshot
	# name: Name of snapshot file
	def save_snapshot(self, name):
		pass


	# Function to load snapshot into graph
	# name: Name of snapshot file
	def load_snapshot(self, name):
		pass


	