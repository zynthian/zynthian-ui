
zynthian_layer => zynthian_node
---------------------------------

	def refresh(self):
		if self.refresh_flag:
			self.refresh_flag=False
			self.refresh_controllers()

			#TODO: Improve this Dirty Hack!!
			#if self.engine.nickname=='MD':
			#	self.zyngui.screens['preset'].fill_list()
			#	if self.zyngui.active_screen=='bank':
			#		if self.preset_name:
			#			self.zyngui.show_screen('control')
			#		else:
			#			self.zyngui.show_screen('preset')

			#self.zyngui.refresh_screen()


	# ---------------------------------------------------------------------------
	# MIDI chan Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, midi_chan):
		self.midi_chan=midi_chan
		self.engine.set_midi_chan(self)
		for zctrl in self.controllers_dict.values():
			zctrl.set_midi_chan(midi_chan)
		for index, output in enumerate(self.audio_out):
			if output.startswith("zynmixer:input_"):
				self.audio_out[index] = "zynmixer:input_%02d%s"%(midi_chan + 1, output[-1:])
		self.zyngui.zynautoconnect_audio()

	def get_midi_chan(self):
		return self.midi_chan





zynthian_engine
----------------

		self.learned_cc = [[None for c in range(128)] for chan in range(16)]
		self.learned_zctrls = {}

		self.options = {
			'clone': True,
			'note_range': True,
			'audio_route': True,
			'midi_chan': True,
			'replace': True,
			'drop_pc': False,
		}


		set_bank =>
		self.zyngui.zynmidi.set_midi_bank_msb(layer.get_midi_chan(), bank[1])


		set_preset =>
		if isinstance(preset[1],int):
			self.zyngui.zynmidi.set_midi_prg(layer.get_midi_chan(), preset[1])
		else:
			self.zyngui.zynmidi.set_midi_preset(layer.get_midi_chan(), preset[1][0], preset[1][1], preset[1][2])

