
import os
import tkinter
from PIL import Image, ImageTk #, ImageDraw, ImageFont
from io import BytesIO
try:
	import cairosvg
except:
	cairosvg = None
# Zynthian specific modules
from zyngui import zynthian_gui_config

BUTTONS = {
	# labels, ZYNSWITCH number, wsLED number, two state button (not used)
	'OPT_ADMIN': ({'default': 'OPT/ADMIN'}, 4, 0, True),
	'MIX_LEVEL': ({'default': 'MIX/LEVEL'}, 5, 1, True),
	'CTRL_PRESET': ({'default': 'CTRL/PRESET'}, 6, 2, True),
	'ZS3_SHOT': ({'default': 'ZS3/SHOT'}, 7, 3, True),
	'METRONOME': ({'default': '_icons/metronome.svg'}, 9, 6, False),
	'PAD_STEP': ({'default': 'PAD/STEP'}, 10, 5, True),
	'ALT': ({'default': 'Alt'}, 8, 4, False),

	'REC': ({'default': '\uf111'}, 12, 8, False),
	'STOP': ({'default': '\uf04d'}, 13, 9, False),
	'PLAY': ({'default': '\uf04b', 'active': '\uf04c'}, 14, 10, False),

	'UP': ({'default': '\uf077'}, 17, 14, False),
	'DOWN': ({'default': '\uf078'}, 21, 17, False),
	'LEFT': ({'default': '\uf053'}, 20, 16, False),
	'RIGHT': ({'default': '\uf054'}, 22, 18, False),
	'SEL_YES': ({'default': 'SEL/YES'}, 18, 13, False),
	'BACK_NO': ({'default': 'BACK/NO'}, 16, 15, False),

	'F1': ({'default': 'F1', 'alt': 'F5'}, 11, 7, False),
	'F2': ({'default': 'F2', 'alt': 'F6'}, 15, 11, False),
	'F3': ({'default': 'F3', 'alt': 'F7'}, 19, 12, False),
	'F4': ({'default': 'F4', 'alt': 'F8'}, 23, 19, False)
}

FKEY2SWITCH = [ BUTTONS['F1'][1], BUTTONS['F2'][1], BUTTONS['F3'][1], BUTTONS['F4'][1]]

LED2BUTTON = {btn[2]: btn[1]-4 for btn in BUTTONS.values()}

LAYOUT_RIGHT = {
    'SIDE' : (
		('OPT_ADMIN', 'MIX_LEVEL'),
		('CTRL_PRESET', 'ZS3_SHOT'),
		('METRONOME', 'PAD_STEP'),
		('BACK_NO', 'SEL_YES'),
		('UP', 'ALT'),
		('DOWN', 'RIGHT') 
	),
	'BOTTOM': ('F1', 'F2', 'F3', 'F4', 'REC', 'STOP', 'PLAY', 'LEFT')
}

LAYOUT_LEFT = {
    'SIDE' : (
		('OPT_ADMIN', 'MIX_LEVEL'),
		('CTRL_PRESET', 'ZS3_SHOT'),
		('METRONOME', 'PAD_STEP'),
		('BACK_NO', 'SEL_YES'),
		('ALT', 'UP'),
		('LEFT', 'DOWN') 
	),
	'BOTTOM': ('RIGHT', 'REC', 'STOP', 'PLAY', 'F1', 'F2', 'F3', 'F4')
}


class zynthian_gui_touchkeypad_v5:

	def __init__(self, parent, side_width, left_side=True):
		"""
		Parameters
		----------
		parent : tkinter widget
			Parent widget
		side_width : int
			Width of the side panel: base for the geometry
		left_side : bool
			Left or right side layout for the side frame
		"""
		self.shown = False
		self.side_frame_width = side_width
		self.bottom_frame_width = zynthian_gui_config.display_width - self.side_frame_width
		self.side_frame_col = 0 if left_side else 1
		self.bottom_frame_col = 1 if left_side else 0
		self.font_size = zynthian_gui_config.font_size
		# only needed for composition of images from text labels
		# self.font1 = ImageFont.truetype("Audiowide-Regular.ttf", size=int(1.4*self.font_size)) # zynthian_gui_config.font_buttonbar[0], size=zynthian_gui_config.font_buttonbar[1])
		# self.font2 = ImageFont.truetype("Audiowide-Regular.ttf", size=int(1.1*self.font_size))

		# configure side frame for 2x6 buttons
		self.side_frame = tkinter.Frame(parent,
			width=self.side_frame_width,
			height=zynthian_gui_config.display_height,
			bg=zynthian_gui_config.color_bg)
		for column in range(2):
			self.side_frame.columnconfigure(column, weight=1)
		for row in range(6):
			self.side_frame.rowconfigure(row, weight=1)

		# 2 columns by 6 buttons at the full diplay height and requested side frame width
		self.side_button_width = self.side_frame_width // 2
		self.side_button_height = zynthian_gui_config.display_height // 6

		# configure bottom frame for a single row of 8 buttons
		self.bottom_frame = tkinter.Frame(parent,
			width=self.bottom_frame_width,
			# the height must correspond to the height of buttons in the side frame
			height=zynthian_gui_config.display_height // 6,
			bg=zynthian_gui_config.color_bg)
		for column in range(8):
			self.bottom_frame.columnconfigure(column, weight=1)
		self.bottom_frame.rowconfigure(0, weight=1)
		
		# select layout as requested
		layout = LAYOUT_LEFT if left_side else LAYOUT_RIGHT
		
		# buffers to remember the buttons and their contents and state
		self.buttons = [None] * 20  # actual button widgets
		self.btndefs = [None] * 20  # original definition of the button parameters
		self.images = [None] * 20   # original image/icon used (if any)
		self.btnstate = [None] * 20 # last state of the button (<=color)
		self.tkimages = [None] * 20 # current image in tkinter format (remember it or the image will be discarded by the garbage collector!)

		# create side frame buttons
		for row in range(6):
			for col in range(2):
				btn = BUTTONS[layout['SIDE'][row][col]]
				zynswitch = btn[1]
				n = zynswitch - 4
				label = btn[0]['default']
				pady = (1,0) if row == 5 else (0,0) if row == 4 else (0,1)
				padx = (0,1) if left_side else (1,0)
				self.btndefs[n] = btn
				self.buttons[n] = self.add_button(n, self.side_frame, row, col, zynswitch, label, padx, pady)
		# create bottom frame buttons
		for col in range(8):
			btn = BUTTONS[layout['BOTTOM'][col]]
			zynswitch = btn[1]
			n = zynswitch - 4
			label = btn[0]['default']
			padx = (0,0) if col == 7 else (0,1)
			self.btndefs[n] = btn
			self.buttons[n] = self.add_button(n, self.bottom_frame, 0, col, zynswitch, label, padx, (1,0))

		# update with user settings from the environment
		self.apply_user_config()


	def add_button(self, n, parent, row, column, zynswitch, label, padx, pady):
		"""
		Create button

		Parameters:
		-----------
		n : int
			Number of the button
		parent : tkinter widget
			Parent widget
		row : int
		column : int
			Position of the button in the grid
		zynswitch : int
			Number of the zynswitch to emulate
		label : str
			Default label for the button
		padx : (int, int)
		pady : (int, int)
			Button padding
		"""
		button = tkinter.Button(
			parent,
			width= 1, # if not label.startswith('_') else self.side_button_width,
			height= 1, # if not label.startswith('_') else self.side_button_height,
			bg=zynthian_gui_config.color_bg,
			fg=zynthian_gui_config.color_header_tx,
			activebackground=zynthian_gui_config.color_panel_bg,
			activeforeground=zynthian_gui_config.color_header_tx,
			highlightbackground=zynthian_gui_config.color_panel_bg,
			highlightcolor=zynthian_gui_config.color_bg,
			highlightthickness=1,
			bd=0,
			relief='flat')
		# set default button state (<=color)
		self.btnstate[n] = zynthian_gui_config.color_header_tx
		if label.startswith('_'):
			# button contains an icon/image instead of a label
			img_name = label[1:]
			if img_name.endswith('.svg'):
				# convert SVG icon into PNG of appropriate size
				if cairosvg:
					png = BytesIO()
					cairosvg.svg2png(url=img_name, write_to=png, output_width=int(1.2*zynthian_gui_config.font_size))
				else:
					png = img_name[:-4]+".png"
				image = Image.open(png)
			else:
				# PNG icons can be imported directly
				image = Image.open(img_name)
			# at least fo image icons, it is useful to store the original image for the purpose of later changes of color
			self.images[n] = image
			tkimage = ImageTk.PhotoImage(image)
			# if we don't keep the image in the object, it will be discarded by garbage collection at the end of this method!
			self.tkimages[n] = tkimage
			button.config(image=tkimage, text='')
		else:
			# if "/" in label:
			#	# two level/lines text label - drawn as image
			# 	line1, line2 = label.split('/')
			# 	image = self.text2image(line1, line2, 'white', 'white', 'white')
			# 	self.images[n] = image
			# 	tkimage = ImageTk.PhotoImage(image)
			# 	self.tkimages[n] = tkimage
			# 	button.config(image=tkimage, text='')
			# else:
			# button has a simple text label: either standard text or an icon included in the "forkawesome" font (unicode char >= \uf000)
			button.config(font=("forkawesome", int(1*zynthian_gui_config.font_size)) if label[0] >= '\uf000' else (zynthian_gui_config.font_family, int(0.9*zynthian_gui_config.font_size)),
			text=label.replace('/', "\n"))
		button.grid_propagate(False)
		button.grid(row=row, column=column, sticky='nswe', padx=padx, pady=pady)
		button.bind('<ButtonPress-1>', lambda e: self.cb_button_push(zynswitch, e))
		button.bind('<ButtonRelease-1>', lambda e: self.cb_button_release(zynswitch, e))
		return button
	
	# def text2image(self, line1, line2, color, color1, color2):
	#	"""
	#	Create image from two lines of labels with a horizontal bar (line) inbetween
	# 	"""
	# 	sizex = self.side_button_width - 4
	# 	sizey = self.side_button_height - 4 # int(5*self.font_size)
	# 	image = Image.new("RGBA", (sizex, sizey), "#00000000")
	# 	d = ImageDraw.Draw(image)
	# 	x = sizex // 2
	# 	d.text((x, (sizey//2)-(self.font_size//1.5)), line1, font=self.font1, fill=color1, anchor="ms")
	# 	d.text((x, (sizey//2)+(self.font_size//1.5)), line2, font=self.font2, fill=color2, anchor="mt")
	# 	d.line([(self.font_size//2,sizey//2), (sizex-(self.font_size//2),sizey//2)], fill=color, width=2)
	# 	return image

	def cb_button_push(self, n, event):
		"""
		Call ZYNSWITCH Push CUIA on button push
		"""
		zynthian_gui_config.zyngui.cuia_queue.put_nowait(f"zynswitch {n},P")

	def cb_button_release(self, n, event):
		"""
		Call ZYNSWITCH Release CUIA on button release
		"""
		zynthian_gui_config.zyngui.cuia_queue.put_nowait(f"zynswitch {n},R")

	def set_button_color(self, led_num, color, mode):
		"""
		Change color of a button according to the wsleds signal

		Parameters
		----------

		led_num : int
			Number of the RGB wsled corresponding to the button
		color : int
			Color requested by the wsled system
		mode : str
			A wanna-be abstraction (string name) of the mode/state - currently just derived from the requested color
			by the `wsleds_v5touch` "fake NeoPixel" emulator
		"""
		# get the button number associated with the wsled number
		n = LED2BUTTON[led_num]
		# don't bother with update if nothing has really changed (redrawing images causes visible blinking!)
		if self.btnstate[n] == (mode or color):
			return
		self.btnstate[n] = mode or color
		# in case the color is still the original wsled integer number, convert it
		label = self.btndefs[n][0]['default']
		# twostate = self.btndefs[n][4]
		if  label.startswith('_'): # self.buttons[n].config()['image'][4]=='':
			# image buttons must be recomposed to change the foreground color
			image = self.images[n]
			mask = image.convert("LA")
			bgimage = Image.new("RGBA", image.size, color)
			fgimage = Image.new("RGBA", image.size, (0,0,0,0))
			composed = Image.composite(bgimage, fgimage, mask)
			tkimage = ImageTk.PhotoImage(composed)
			self.tkimages[n] = tkimage
			self.buttons[n].config(image=tkimage)
		# elif '/' in label:
		#		# two level button labels with multiple colors must redraw the whole image
		# 		line1, line2 = label.split('/')
		# 		color0 = color1 = color2 = color
		# 		if twostate and zynthian_gui_config.zyngui:
		# 			color0 = zynthian_gui_config.zyngui.wsleds.wscolor_default
		# 			color1 = zynthian_gui_config.zyngui.wsleds.wscolor_active if mode == 'active' else zynthian_gui_config.zyngui.wsleds.wscolor_default
		# 			color2 = zynthian_gui_config.zyngui.wsleds.wscolor_active2 if mode == 'active2' else zynthian_gui_config.zyngui.wsleds.wscolor_default
		# 		image = self.text2image(line1, line2, color0, color1, color2)
		# 		self.images[n] = image
		# 		tkimage = ImageTk.PhotoImage(image)
		# 		self.tkimages[n] = tkimage
		# 		self.buttons[n].config(image=tkimage, text='')
		else:
			# plain text labels may just change the color and possibly also its label if a special label 
			# is associated with the requested mode (<=color) in the button definition
			self.refresh_button_label(n, mode)
			self.buttons[n].config(fg=color)

	def refresh_button_label(self, n, mode):
			text = self.btndefs[n][0].get(mode, self.btndefs[n][0]['default']).replace('/', "\n")
			self.buttons[n].config(text=text)

	def show(self):
		if not self.shown:
			self.side_frame.grid_propagate(False)
			self.side_frame.grid(row=0, column=self.side_frame_col, rowspan=2, sticky="nws")
			self.bottom_frame.grid_propagate(False)
			self.bottom_frame.grid(row=1, column=self.bottom_frame_col, sticky="wse")
			self.shown = True

	def hide(self):
		if self.shown:
			self.side_frame.grid_remove()
			self.bottom_frame.grid_remove()
			self.shown = False

	def apply_user_config(self):
		for n in range(0, 20):
			default = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_LABEL_{:02d}_DEFAULT'.format(n+1), None)
			alt = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_LABEL_{:02d}_ALT'.format(n+1), None)
			active = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_LABEL_{:02d}_ACTIVE'.format(n+1), None)
			active2 = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_LABEL_{:02d}_ACTIVE2'.format(n+1), None)
			if default:
				self.btndefs[n][0]['default'] = default
			if alt:
				self.btndefs[n][0]['alt'] = alt
			if active:
				self.btndefs[n][0]['active'] = active
			if active2:
				self.btndefs[n][0]['active2'] = active2

	def _fkey2btn(self, n):
		mode = 'default'
		if n >= 4:
			mode = 'alt'
			n -= 4
		return (FKEY2SWITCH[n]-4, mode)

	def set_fkey_label(self, n, label):
		btn, mode = self._fkey2btn(n)
		self.btndefs[btn][0][mode] = label
		self.refresh_button_label(btn, label)

	def get_fkey_label(self, n):
		btn, mode = self._fkey2btn(n)
		return self.btndefs[btn][0][mode]


	# def set_button_label(self, n, mode, label):
	# 	"""
	# 	Dynamic label updates
	# 	"""
	# 	self.btndefs[n][mode] = label
	# 	self.refresh_button_label(n, self.btnstate[n])