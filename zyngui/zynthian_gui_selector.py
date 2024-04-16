#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Selector Base Class
# 
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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

import logging
import tkinter
from datetime import datetime

# Zynthian specific modules
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngine import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui.zynthian_gui_controller import zynthian_gui_controller

# ------------------------------------------------------------------------------
# Zynthian Listbox Selector GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_selector(zynthian_gui_base):

	# Scale for listbox swipe action after-roll
	swipe_roll_scale = [1, 0, 1, 1, 2, 2, 2, 4, 4, 4, 4, 4] #1, 0, 1, 0, 1, 0, 1, 0,

	def __init__(self, selcap='Select', wide=False, loading_anim=True):
		super().__init__()

		# If the children class has not defined a custom GUI layout, use the default from config
		if not hasattr(self, 'layout'):
			self.layout = zynthian_gui_config.layout

		# Default controller width
		if "ctrl_width" not in self.layout:
			self.layout['ctrl_width'] = 0.25

		self.index = 0
		self.scroll_y = 0
		self.list_data = []
		self.zselector = None
		self.zselector_hidden = False
		self.swipe_speed = 0
		self.list_entry_height = int(1.8 * zynthian_gui_config.font_size)  # Set approx. here to avoid errors. Set accurately when list item selected
		self.listbox_motion_last_dy = 0
		self.swiping = False
		self.last_release = datetime.now()
		self.last_selected_index = None

		# ListBox
		self.listbox = tkinter.Listbox(self.main_frame,
			font=zynthian_gui_config.font_listbox,
			bd=7,
			highlightthickness=0,
			relief='flat',
			bg=zynthian_gui_config.color_panel_bg,
			fg=zynthian_gui_config.color_panel_tx,
			selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			selectmode=tkinter.SINGLE)

		# Configure layout
		for ctrl_pos in self.layout['ctrl_pos']:
			self.main_frame.rowconfigure(ctrl_pos[0], weight=1, uniform='btn_row')
		self.main_frame.columnconfigure(self.layout['list_pos'][1], weight=3)
		self.main_frame.columnconfigure(self.layout['list_pos'][1] + 1, weight=1)

		# Row 4 expands to fill unused space
		#self.main_frame.rowconfigure(4, weight=1) #TODO: Validate row 4 is still required after chagnes to layout implementation (BW)

		if self.layout['columns'] == 3:
			self.wide = wide
		else:
			self.wide = True
		if self.wide:
			padx = (0, 2)
		else:
			padx = (2, 2)
		if self.buttonbar_config:
			pady = (0, 1)
		else:
			pady = (0, 0)
		self.listbox.grid(row=self.layout['list_pos'][0], column=self.layout['list_pos'][1], rowspan=4, padx=padx, pady=pady, sticky="news")

		# Bind listbox events
		self.listbox_push_ts = datetime.now()
		self.listbox.bind("<Button-1>",self.cb_listbox_push)
		self.listbox.bind("<ButtonRelease-1>",self.cb_listbox_release)
		self.listbox.bind("<B1-Motion>",self.cb_listbox_motion)
		self.listbox.bind("<Button-4>",self.cb_listbox_wheel)
		self.listbox.bind("<Button-5>",self.cb_listbox_wheel)
		#self.listbox.bind('<<ListboxSelect>>', cb_select)

		if loading_anim:
			# Canvas for loading image animation
			self.loading_canvas = tkinter.Canvas(self.main_frame,
				width=1, #zynthian_gui_config.fw2, #self.width // 4 - 2,
				height=1, #zynthian_gui_config.fh2, #self.height // 2 - 1,
				bd=0,
				highlightthickness=0,
				bg = zynthian_gui_config.color_bg)
			# Position at top of column containing selector
			self.loading_canvas.grid(row=0, column=self.layout['list_pos'][1] + 1, rowspan=2, sticky="news")
			self.loading_push_ts = None
			self.loading_canvas.bind("<Button-1>", self.cb_loading_push)
			self.loading_canvas.bind("<ButtonRelease-1>", self.cb_loading_release)

			# Setup Loading Logo Animation
			self.loading_index = 0
			self.loading_item = self.loading_canvas.create_image(3, 3, image=zynthian_gui_config.loading_imgs[0], anchor=tkinter.NW)
		else:
			self.loading_canvas = None
			self.loading_index = 0
			self.loading_item = None

		# Selector Controller Caption
		self.selector_caption = selcap

		self.show_sidebar(True)

	def update_layout(self):
		super().update_layout()
		ctrl_width = self.width * self.layout['ctrl_width'] * self.sidebar_shown
		if self.layout['columns'] == 2:
			lb_width = int(self.width - ctrl_width)
			lb_weight = 3
		else:
			lb_width = int(self.width - 2 * ctrl_width)
			lb_weight = 2
		ctrl_width = int(ctrl_width)
		self.main_frame.columnconfigure(self.layout['list_pos'][1], minsize=lb_width, weight=lb_weight)
		self.main_frame.columnconfigure(self.layout['list_pos'][1] + 1, minsize=ctrl_width, weight=self.sidebar_shown)

	def build_view(self):
		self.fill_list()
		self.set_selector()
		self.set_select_path()
		return True

	def show_sidebar(self, show):
		self.sidebar_shown = show
		if show:
			if self.zselector and not self.zselector_hidden:
				self.zselector.grid()
			if self.loading_canvas:
				self.loading_canvas.grid()
		else:
			if self.zselector and not self.zselector_hidden:
				self.zselector.grid_remove()
			if self.loading_canvas:
				self.loading_canvas.grid_remove()
		self.update_layout()

	def refresh_loading(self):
		if self.shown and self.loading_canvas:
			try:
				if self.zyngui.state_manager.is_busy():
					self.loading_index += 1
					if self.loading_index > len(zynthian_gui_config.loading_imgs) + 1:
						self.loading_index = 0
					self.loading_canvas.itemconfig(self.loading_item, image=zynthian_gui_config.loading_imgs[self.loading_index])
				else:
					self.reset_loading()
			except:
				self.reset_loading()

	def reset_loading(self, force=False):
		if self.loading_canvas and (self.loading_index>0 or force):
			self.loading_index=0
			self.loading_canvas.itemconfig(self.loading_item, image=zynthian_gui_config.loading_imgs[0])

	def fill_listbox(self):
		self.listbox.delete(0, tkinter.END)
		if not self.list_data:
			self.list_data = []
		for i, item in enumerate(self.list_data):
			label = item[2]
			if len(item) > 5 and isinstance(item[5], str):
				label += item[5]
			self.listbox.insert(tkinter.END, label)
			if item[0] is None:
				self.listbox.itemconfig(i, {'bg': zynthian_gui_config.color_panel_hl, 'fg': zynthian_gui_config.color_tx_off})
			# Can't find any engine currently using this "format" feature:
			#last_param = item[len(item) - 1]
			#if isinstance(last_param, dict) and 'format' in last_param:
			#	self.listbox.itemconfig(i, last_param['format'])

	def set_selector(self, zs_hidden=True):
		self.zselector_hidden = zs_hidden
		if self.zselector:
			self.zselector.zctrl.set_options({'symbol': self.selector_caption, 'name': self.selector_caption, 'short_name': self.selector_caption, 'value_min': 0, 'value_max': len(self.list_data) - 1, 'value': self.index })
			self.zselector.config(self.zselector.zctrl)
			self.zselector.show()
		else:
			zselector_ctrl = zynthian_controller(None ,self.selector_caption, {'value_min': 0, 'value_max': len(self.list_data) - 1, 'value': self.index})
			self.zselector = zynthian_gui_controller(zynthian_gui_config.select_ctrl, self.main_frame, zselector_ctrl, zs_hidden, selcounter=True, orientation=self.layout['ctrl_orientation'])
		if not self.zselector_hidden:
			self.zselector.grid(row=self.layout['ctrl_pos'][3][0], column=self.layout['ctrl_pos'][3][1], sticky="news")

	def plot_zctrls(self):
		self.swipe_update()
		if self.zselector_hidden:
			return
		if self.zselector.zctrl.is_dirty:
			self.zselector.calculate_plot_values()
		self.zselector.plot_value()

	def swipe_nudge(self, dts):
		self.swipe_speed = int(len(self.swipe_roll_scale) - ((dts - 0.02) / 0.06) * len(self.swipe_roll_scale))
		self.swipe_speed = min(self.swipe_speed, len(self.swipe_roll_scale) - 1)
		self.swipe_speed = max(self.swipe_speed, 0)

	def swipe_update(self):
		if self.swipe_speed > 0:
			self.swipe_speed -= 1
			self.listbox.yview_scroll(self.swipe_dir * self.swipe_roll_scale[self.swipe_speed], tkinter.UNITS)

	def fill_list(self):
		self.fill_listbox()
		self.select()
		self.last_index_change_ts = datetime.min

	def update_list(self):
		if self.shown:
			yv = self.listbox.yview()
			self.fill_list()
			self.set_selector()
			self.listbox.yview_moveto(yv[0])

	def get_cursel(self):
		cursel = self.listbox.curselection()
		if (len(cursel) > 0):
			index = int(cursel[0])
		else:
			index = 0
		return index

	def select_listbox(self, index, see=True):
		if index < 0:
			index = 0
		elif index >= len(self.list_data):
			index = len(self.list_data) - 1
		index = self.skip_separators(index)
		# Set selection
		self.listbox.selection_clear(0, tkinter.END)
		if index is None:
			return
		self.listbox.selection_set(index)
		# Set window
		if see:
			self.listbox.yview_moveto(self.scroll_y) # Restore vertical position
			# Show next/previous item when scrolling but ensure selected item is in view
			self.listbox.see(index + 1)
			self.listbox.see(index - 1)
			self.listbox.see(index)
			self.scroll_y = self.listbox.yview()[0] # Save vertical position
			if self.listbox.bbox(index):
				self.list_entry_height = self.listbox.bbox(index)[3]
		# Set index value
		self.index = index
		self.last_index_change_ts = datetime.now()

	def select_listbox_by_name(self, name):
		names = self.listbox.get(0, self.listbox.size())
		try:
			index = names.index(name)
			self.select(index)
		except:
			logging.debug("%s is not in listbox", name)

	def skip_separators(self, index):
		# Separators have 'None' as  first data element
		if index >= 0 and index < len(self.list_data) and self.list_data[index][0] is None:
			# Request to select a blank list entry
			if self.index <= index:
				# Request is higher than current entry so try to move down list
				for i in range(index, len(self.list_data)):
					if self.list_data[i][0] is not None:
						return i
				# No entries down list so let's search back up
				for i in range(index, -1, -1):
					if self.list_data[i][0] is not None:
						return i
			else:
				# Request is lower than current entry so try to move up list
				for i in range(index, -1, -1):
					if self.list_data[i][0] is not None:
						return i
				# No entires up list so let's search back down
				for i in range(index, len(self.list_data)):
					if self.list_data[i][0] is not None:
						return i
			return None # No valid entries in the listbox - must all be titles
		return index

	def select(self, index=None):
		if index is None:
			index = self.index
		self.select_listbox(index)
		if self.shown and self.zselector and self.zselector.zctrl.value != self.index:
			self.zselector.zctrl.set_value(self.index, False)
			self.last_index_change_ts = datetime.now()

	def click_listbox(self, index=None, t='S'):
		if index is not None:
			self.select(index)
		else:
			self.select(self.get_cursel())

		self.select_action(self.index, t)

	# Function to handle select switch press
	# t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	def switch_select(self, t='S'):
		# This is SUPERUGLY!!! I really don't like parameter editor implemented in the base class.
		if super().switch_select(t):
			return True

		self.click_listbox(None, t)
		return True


	def select_action(self, index, t='S'):
		self.last_selected_index = index

	# --------------------------------------------------------------------------
	# Zynpot Callbacks (rotaries!)
	# --------------------------------------------------------------------------

	def zynpot_cb(self, i, dval):
		# This is SUPERUGLY!!! I really don't like parameter editor implemented in the base class.
		if super().zynpot_cb(i, dval):
			return True

		if self.shown and self.zselector and self.zselector.index == i:
			self.zselector.zynpot_cb(dval)
			if self.index != self.zselector.zctrl.value:
				self.select(self.zselector.zctrl.value)
			return True
		return False

	def arrow_up(self):
		self.select(self.index - 1)

	def arrow_down(self):
		self.select(self.index + 1)

	# --------------------------------------------------------------------------
	# Keyboard & Mouse/Touch Callbacks
	# --------------------------------------------------------------------------

	def cb_listbox_push(self,event):
		if self.zyngui.cb_touch(event):
			return "break"

		self.listbox_push_ts = datetime.now() # Timestamp of initial touch
		#logging.debug("LISTBOX PUSH => %s" % (self.listbox_push_ts))
		self.listbox_y0 = event.y # Touch y-coord of initial touch
		self.listbox_x0 = event.x  # Touch x-coord of initial touch
		self.swiping = False # True if swipe action in progress (disables press action)
		self.swipe_speed = 0 # Speed of swipe used for rolling after release
		return "break" # Don't select entry on push

	def cb_listbox_release(self, event):
		if self.zyngui.cb_touch_release(event):
			return "break"

		now = datetime.now()
		dts = (now - self.listbox_push_ts).total_seconds()
		rdts = (now - self.last_release).total_seconds()
		self.last_release = now
		if self.swiping:
			self.swipe_nudge(dts)
		else:
			if rdts < 0.03:
				return  # Debounce
			cursel = self.listbox.nearest(event.y)
			if self.index != cursel:
				self.select(cursel)
			if dts < zynthian_gui_config.zynswitch_bold_seconds:
				self.zyngui.zynswitch_defered('S', 3)
			elif zynthian_gui_config.zynswitch_long_seconds > dts >= zynthian_gui_config.zynswitch_bold_seconds:
				self.zyngui.zynswitch_defered('B', 3)

	def cb_listbox_motion(self, event):
		dy = self.listbox_y0 - event.y
		offset_y = int(dy / self.list_entry_height)
		if offset_y:
			self.swiping = True
			self.listbox.yview_scroll(offset_y, tkinter.UNITS)
			self.swipe_dir = abs(dy) // dy
			self.listbox_y0 = event.y + self.swipe_dir * (abs(dy) % self.list_entry_height)
			self.listbox_push_ts = datetime.now()  # Use time delta between last motion and release to determine speed of swipe

	def cb_listbox_wheel(self, event):
		if event.num == 5 or event.delta == -120:
			self.select(self.index + 1)
		elif event.num == 4 or event.delta == 120:
			self.select(self.index - 1)
		return "break"  # Consume event to stop scrolling of listbox

	def cb_loading_push(self, event):
		self.loading_push_ts = datetime.now()
		#logging.debug("LOADING PUSH => %s" % self.loading_push_ts)

	def cb_loading_release(self,event):
		if self.loading_push_ts:
			if zynthian_gui_config.enable_touch_controller_switches:
				dts = (datetime.now()-self.loading_push_ts).total_seconds()
				logging.debug("LOADING RELEASE => %s" % dts)
				if dts < zynthian_gui_config.zynswitch_bold_seconds:
					self.zyngui.zynswitch_defered('S', 2)
				elif dts >= zynthian_gui_config.zynswitch_bold_seconds and dts < zynthian_gui_config.zynswitch_long_seconds:
					self.zyngui.zynswitch_defered('B', 2)
				elif dts >= zynthian_gui_config.zynswitch_long_seconds:
					self.zyngui.zynswitch_defered('L', 2)

# ------------------------------------------------------------------------------
