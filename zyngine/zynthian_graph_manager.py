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
# interconnects) and the configuration of each node (synth engine, plugin,
# etc.). The state of the graph can be saved as a snapshot.

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
		self.nodes = [] # List of nodes in graph, each derived from zynthian_engine
		self.links = [] # List of interconnects (src_port, dst_port) Is this required or can be deduced by JACK graph?
		#	Links describe one or more JACK routes. They may be mono or multichannel audio or MIDI.
		#	Each node object is derived zynthian_engine which defines its input and output ports, grouping individual i/o as appropriate to allow automatic connection and rule-based routing decisions, e.g. a mono output connecting to a stereo input will send mono to both
		# Links can be uniquely identified by the source and destination ports. This can be represented within a session with port UUIDs and within snapshot by list of destination ports each source port is connected to.


	# Function to add a node to the graph
	# node: Object of type zynthian_engine
	# link: Interconnect to insert new node (Optional - Default: create new chain)
	def add_node(self, node, link=None):
		pass


	# Function to remove a node from the graph
	# node: Object to remove
	# Note: This destroys the node object
	def remove_node(self, node)
		pass


	# Function to move a node within the graph
	# node: Object to move
	# link: Interconnect to insert node
	# Returns: True on success otherwise node is not moved
	# Note: If no more nodes exist in original chain and no input is routed then chain is destroyed
	def move_node(self, node, link):
		pass


	# Function to remove chain from graph
	# chain: Index of chain to remove
	# Note: This destroys all nodes in the chain
	def remove_chain(self, index):
		pass


	# Function to remove all chains from graph
	# Note: This destroys all nodes in all chains
	def reset(self, index):
		pass
	

	# Function to get the id of an interconnect
	# source_node: Source object of link
	# source_port: Port on source object that link connects
	# destination_node: Destination object of link
	# destination_port: Port on destination object that link connects
	# Returns: id of link or None if link does not exist
	def get_interconnect(self, source_node, source_port, destination_node, destination_port):
		return None


	# Function to get list of chains
	def get_chains(self):
		return []


	# Function to get list of nodes in a chain
	# chain: id of chain to query
	def get_nodes(self, chain):
		return []


	# Function to get list of inputs to a node
	# node: Object whose inputs are being queried
	# Returns: List of inputs
	def get_node_inputs(self, node):
		return []


	# Function to get list of outputs from a node
	# node: Object whose outputs are being queried
	# Returns: List of outputs
	def get_node_outputs(self, node):
		return []


	# Function to get list of interconnects to a node input
	# node: Object whose input is being queried
	# input: id of node input
	def get_input_links(self, node, input):
		return []


	# Function to get list of interconnects from a node output
	# node: Object whose output is being queried
	# input: id of node output
	def get_input_links(self, node, output):
		return []


	# Function to save graph as a snapshot
	# name: Name of snapshot file
	def save_snapshot(self, name):
		pass


	# Function to load snapshot into graph
	# name: Name of snapshot file
	def load_snapshot(self, name):
		pass


	