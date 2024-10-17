#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Zynthian Audio Player" (zynaudioplayer#one)
#
# Copyright (C) 2022 Brian Walton <riban@zynthian.org>
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

import liblo
import tkinter
import logging
from turtle import pos
from threading import Timer
from functools import partial

from zyngine.zynthian_engine import zynthian_engine
from zyngine.zynthian_engine_sooperlooper import *
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base


class zynthian_widget_sooperlooper(zynthian_widget_base.zynthian_widget_base):

    SLIDER_BG = zynthian_gui_config.color_panel_bg
    SLIDER_FG = '#26b'
    SLIDER_TEXT = zynthian_gui_config.color_tx_off
    BUTTON_ASSERTED = zynthian_gui_config.color_low_on

    def __init__(self, parent):
        super().__init__(parent)

        self.slider_press_event = None
        self.state = 0
        self.selected_loop = 0
        self.loop_count = 0
        self.click_timer = None

        self.row_height = 20
        self.flash_count = 0

        if zynthian_gui_config.layout['columns'] <= 2:
            self.font_size_sl = zynthian_gui_config.font_size
        else:
            # TODO: Use better font scaling based on screen resolution
            self.font_size_sl = int(0.7 * zynthian_gui_config.font_size)

        self.tri_size = int(0.5 * zynthian_gui_config.font_size)
        # int(0.70 * self.font_size_sl)
        txt_y = zynthian_gui_config.display_height // 22
        self.txt_x = 4

        self.pos_canvas = []
        for loop in range(zynthian_engine_sooperlooper.MAX_LOOPS):
            pos_canvas = tkinter.Canvas(self,
                                        height=1,
                                        bd=0,
                                        highlightthickness=0,
                                        bg=self.SLIDER_BG)
            pos_label = pos_canvas.create_text(
                self.txt_x, txt_y,
                fill=self.SLIDER_TEXT,
                text='0.0/0.0',
                anchor='w',
                # font=("source code pro", self.font_size_sl, 'bold')
                # font=("office code pro", self.font_size_sl, 'bold')
                font=("monoid", int(0.9 * self.font_size_sl))
                # font=("share tech mono", self.font_size_sl)
            )
            pos_line = pos_canvas.create_line(
                0, 0, 0, self.row_height,
                fill='#ff0',
                width=2
            )
            pos_border = pos_canvas.create_rectangle(
                2, 2, 2, 2,
                width=2,
                outline=zynthian_gui_config.color_on,
                state=tkinter.HIDDEN)

            mute_canvas = tkinter.Canvas(self,
                                         height=self.row_height,
                                         bd=0,
                                         highlightthickness=0,
                                         bg=self.SLIDER_BG
                                         )
            mute_text = mute_canvas.create_text(
                self.txt_x, txt_y,
                fill=self.SLIDER_TEXT,
                text='mute',
                font=(zynthian_gui_config.font_family, self.font_size_sl)
            )
            self.pos_canvas.append({'canvas': pos_canvas, 'border': pos_border, 'label': pos_label,
                                   'line': pos_line, 'mute': mute_canvas, 'mute_text': mute_text})
            pos_canvas.bind("<ButtonPress-1>", self.on_loop_click)
            pos_canvas.bind("<ButtonRelease-1>", self.on_loop_release)
            mute_canvas.bind("<ButtonPress-1>", self.on_loop_click)

        self.add_canvas = tkinter.Canvas(self,
                                         height=self.row_height,
                                         bd=0,
                                         highlightthickness=0,
                                         bg=self.SLIDER_BG
                                         )
        self.add_text = self.add_canvas.create_text(
            self.txt_x, txt_y,
            fill=self.SLIDER_TEXT,
            text='add loop',
            font=(zynthian_gui_config.font_family, self.font_size_sl)
        )
        self.add_canvas.bind('<ButtonPress-1>', self.on_add_click)

        self.input_level_canvas = tkinter.Canvas(self,
                                                 height=1,
                                                 bd=0,
                                                 highlightthickness=0,
                                                 bg=self.SLIDER_BG)
        self.input_level_fg = self.input_level_canvas.create_rectangle(
            0, 0, 0, self.row_height,
            fill='#0a0')
        self.input_level_label = self.input_level_canvas.create_text(
            self.txt_x, txt_y,
            fill=self.SLIDER_TEXT,
            text='input level',
            anchor='w',
            font=(zynthian_gui_config.font_family, self.font_size_sl)
        )
        self.threshold_line = self.input_level_canvas.create_line(
            0, 0, 0, self.row_height,
            fill='#ff0',
            width=2
        )
        self.in_gain_marker = self.input_level_canvas.create_polygon(
            -self.tri_size, 0,
            self.tri_size, 0,
            0, self.tri_size,
            fill='#d00'
        )

        self.wet_canvas = tkinter.Canvas(self,
                                         height=1,
                                         bd=0,
                                         highlightthickness=0,
                                         bg=self.SLIDER_BG)
        self.wet_fg = self.wet_canvas.create_rectangle(
            0, 0, 0, self.row_height,
            fill=self.SLIDER_FG
        )
        self.wet_label = self.wet_canvas.create_text(
            self.txt_x, txt_y,
            fill=self.SLIDER_TEXT,
            text='wet',
            anchor='w',
            font=(zynthian_gui_config.font_family, self.font_size_sl)
        )

        self.dry_canvas = tkinter.Canvas(self,
                                         height=1,
                                         bd=0,
                                         highlightthickness=0,
                                         bg=self.SLIDER_BG)
        self.dry_fg = self.dry_canvas.create_rectangle(
            0, 0, 0, self.row_height,
            fill=self.SLIDER_FG
        )
        self.dry_label = self.dry_canvas.create_text(
            self.txt_x, txt_y,
            fill=self.SLIDER_TEXT,
            text='dry (monitor)',
            anchor='w',
            font=(zynthian_gui_config.font_family, self.font_size_sl)
        )

        self.feedback_canvas = tkinter.Canvas(self,
                                              height=1,
                                              bd=0,
                                              highlightthickness=0,
                                              bg=self.SLIDER_BG)
        self.feedback_fg = self.feedback_canvas.create_rectangle(
            0, 0, 0, self.row_height,
            fill=self.SLIDER_FG
        )
        self.feedback_label = self.feedback_canvas.create_text(
            self.txt_x, txt_y,
            fill=self.SLIDER_TEXT,
            text='feedback',
            anchor='w',
            font=(zynthian_gui_config.font_family, self.font_size_sl)
        )

        self.button_frame = tkinter.Frame(self, bg='#000')
        for col in range(4):
            self.button_frame.columnconfigure(col, weight=1, uniform='btn_col')

        self.buttons = {}
        for i, btn in enumerate(['record', 'overdub', 'multiply', 'replace', 'substitute', 'insert', 'undo', 'redo', 'trigger', 'oneshot', 'reverse', 'pause']):
            if btn == 'substitute':
                fs = int(0.8 * self.font_size_sl)
            else:
                fs = int(self.font_size_sl)

            command = partial(lambda a: self.on_button(a), btn)
            self.buttons[btn] = tkinter.Button(self.button_frame,
                                               text=btn,
                                               background=self.SLIDER_BG,
                                               activebackground=self.SLIDER_BG,
                                               highlightbackground=self.SLIDER_BG,
                                               foreground=self.SLIDER_TEXT,
                                               activeforeground=self.SLIDER_TEXT,
                                               highlightcolor=self.SLIDER_TEXT,
                                               bd=0,
                                               relief=tkinter.FLAT,
                                               overrelief=tkinter.FLAT,
                                               font=(
                                                   zynthian_gui_config.font_family, fs),
                                               command=command,
                                               height=1,
                                               pady=0
                                               )
            row = int(i / 4)
            col = i % 4
            if col == 3:
                padx = (0, 0)
            else:
                padx = (0, 1)
            self.buttons[btn].grid(row=row, column=col,
                                   sticky='news', padx=padx, pady=(0, 1))
            self.button_frame.rowconfigure(row, weight=1, uniform='btn_row')
            self.button_frame.columnconfigure(col, weight=1, uniform='btn_col')

        for col in range(4):
            self.columnconfigure(col, weight=1, uniform='col')
        self.rowconfigure(0, weight=1)

        self.button_frame.grid(columnspan=4, sticky='news')

        for loop in range(zynthian_engine_sooperlooper.MAX_LOOPS):
            self.pos_canvas[loop]['canvas'].grid(
                row=1 + loop, columnspan=3, sticky='news', padx=(0, 1), pady=(0, 1))
            self.pos_canvas[loop]['mute'].grid(
                row=1 + loop, column=3, sticky='news', pady=(0, 1))
            self.pos_canvas[loop]['canvas'].grid_remove()
            self.pos_canvas[loop]['mute'].grid_remove()

        self.add_canvas.grid(row=zynthian_engine_sooperlooper.MAX_LOOPS,
                             columnspan=2, sticky='news', padx=(0, 1), pady=(0, 1))
        self.input_level_canvas.grid(row=1 + zynthian_engine_sooperlooper.MAX_LOOPS,
                                     columnspan=2, sticky='news', padx=(0, 1), pady=(0, 1))
        self.feedback_canvas.grid(row=1 + zynthian_engine_sooperlooper.MAX_LOOPS,
                                  column=2, columnspan=2, sticky='news', pady=(0, 1))
        self.wet_canvas.grid(row=2 + zynthian_engine_sooperlooper.MAX_LOOPS,
                             columnspan=2, sticky='news', padx=(0, 1), pady=(0, 1))
        self.dry_canvas.grid(row=2 + zynthian_engine_sooperlooper.MAX_LOOPS,
                             column=2, columnspan=2, sticky='news', pady=(0, 1))

        self.symbol_map = {
            self.dry_canvas: 'dry',
            self.wet_canvas: 'wet',
            self.feedback_canvas: 'feedback',
            self.input_level_canvas: 'rec_thresh',
        }

        for slider in self.symbol_map:
            slider.bind("<Button-4>", self.on_slider_wheel)
            slider.bind("<Button-5>", self.on_slider_wheel)
            slider.bind("<ButtonPress-1>", self.on_slider_press)
            slider.bind("<ButtonRelease-1>", self.on_slider_release)
            slider.bind("<B1-Motion>", self.on_slider_motion)

    def set_processor(self, processor):
        super().set_processor(processor)
        self.osc_url = 'osc.udp://localhost:{}'.format(
            self.processor.engine.SL_PORT)

    def on_size(self, event):
        super().on_size(event)

        self.row_height = (self.height - zynthian_engine_sooperlooper.MAX_LOOPS -
                           5) // (zynthian_engine_sooperlooper.MAX_LOOPS + 5)
        self.rowconfigure(0, minsize=(self.row_height + 1) * 3)
        for row in range(1, zynthian_engine_sooperlooper.MAX_LOOPS + 3):
            self.rowconfigure(row, minsize=self.row_height)

        txt_xc = (self.width // 8) - 1
        txt_y = self.height // (2 *
                                zynthian_engine_sooperlooper.MAX_LOOPS + 10)
        for pc in self.pos_canvas:
            pc['mute'].coords(pc['mute_text'], txt_xc, txt_y)
            pc['canvas'].coords(pc['label'], self.txt_x, txt_y)
        self.add_canvas.coords(self.add_text, txt_xc * 2, txt_y)
        self.input_level_canvas.coords(
            self.input_level_label, self.txt_x, txt_y)
        self.wet_canvas.coords(self.wet_label, self.txt_x, txt_y)
        self.dry_canvas.coords(self.dry_label, self.txt_x, txt_y)
        self.feedback_canvas.coords(self.feedback_label, self.txt_x, txt_y)

    def on_loop_click(self, event):
        for loop, slider in enumerate(self.pos_canvas):
            if event.widget == slider['canvas']:
                liblo.send(self.osc_url, '/set',
                           ('s', 'selected_loop_num'), ('f', loop))
                self.click_timer = Timer(1.4, self.on_click_timer)
                self.click_timer.start()
                break
            if event.widget == slider['mute']:
                liblo.send(self.osc_url, '/sl/{}/hit'.format(loop),
                           ('s', 'mute'))
                break

    def on_loop_release(self, event):
        if self.click_timer and self.click_timer.is_alive():
            self.click_timer.cancel()

    def on_click_timer(self):
        if self.monitors['loop_count'] > 1:
            self.zyngui.show_confirm("Remove loop {}?".format(
                self.selected_loop + 1), self.remove_loop)

    def on_add_click(self, event):
        liblo.send(self.osc_url, '/loop_add', ('i', 2), ('f', 30), ('i', 0))

    def remove_loop(self, params):
        liblo.send(self.osc_url, '/loop_del', ('i', self.selected_loop))

    def on_button(self, btn):
        if btn in ['undo', 'redo']:
            liblo.send(self.osc_url, '/sl/-3/hit', ('s', btn))
        else:
            self.processor.controllers_dict[btn].toggle()

    def on_slider_wheel(self, event):
        try:
            symbol = self.symbol_map[event.widget]
            if event.num == 5 or event.delta == -120:
                self.processor.controllers_dict[symbol].nudge(-1)
            if event.num == 4 or event.delta == 120:
                self.processor.controllers_dict[symbol].nudge(1)
        except Exception as e:
            logging.warning(e)

    def on_slider_press(self, event):
        self.slider_press_event = event

    def on_slider_release(self, event):
        self.slider_press_event = None

    def on_slider_motion(self, event):
        if self.slider_press_event:
            try:
                symbol = self.symbol_map[event.widget]
                zctrl = self.processor.controllers_dict[symbol]
                zctrl.set_value(
                    zctrl.value + (event.x - self.slider_press_event.x) / event.widget.winfo_width())
                self.slider_press_event = event
            except Exception as e:
                logging.warning(e)

    def refresh_gui(self):
        # TODO: Change GUI on event, not on periodic refresh

        # Update counter used to flash/blink buttons
        self.flash_count -= 1
        if self.flash_count < 0:
            self.flash_count = 7

        # Update quantity of loops
        if self.loop_count != self.monitors['loop_count']:
            self.loop_count = self.monitors['loop_count']
            for loop in range(self.loop_count):
                self.pos_canvas[loop]['canvas'].grid()
                self.pos_canvas[loop]['mute'].grid()
            for loop in range(self.loop_count, zynthian_engine_sooperlooper.MAX_LOOPS):
                self.pos_canvas[loop]['canvas'].grid_remove()
                self.pos_canvas[loop]['mute'].grid_remove()
            if self.loop_count < zynthian_engine_sooperlooper.MAX_LOOPS:
                self.add_canvas.grid()
            else:
                self.add_canvas.grid_remove()

        # Update loop specific parameters
        for loop in range(self.loop_count):
            loop_pos_symbol = 'loop_pos_{}'.format(loop)
            loop_len_symbol = 'loop_len_{}'.format(loop)
            state_symbol = 'state_{}'.format(loop)
            next_state_symbol = 'next_state_{}'.format(loop)
            waiting_symbol = 'waiting_{}'.format(loop)
            if loop_pos_symbol in self.monitors:
                pos = self.monitors[loop_pos_symbol]
            else:
                pos = 0
            if loop_len_symbol in self.monitors:
                len = self.monitors[loop_len_symbol]
            else:
                len = 0
            if state_symbol in self.monitors:
                state = self.monitors[state_symbol]
            else:
                state = 0
            if next_state_symbol in self.monitors:
                next_state = self.monitors[next_state_symbol]
            else:
                next_state = -1
            if waiting_symbol in self.monitors:
                waiting = self.monitors[waiting_symbol]
            else:
                waiting = 0
            if waiting or state in [1, 3]:
                # Pending states
                # TODO: Split to pending rec, pending play, etc.
                bg = '#c90'

            elif state in (SL_STATE_RECORDING, SL_STATE_OVERDUBBING, SL_STATE_MULTIPLYING, SL_STATE_INSERTING, SL_STATE_REPLACING, SL_STATE_DELAYING, SL_STATE_SUBSTITUTING):
                # Record states
                bg = self.BUTTON_ASSERTED

            elif state in (SL_STATE_OFF, SL_STATE_MUTED, SL_STATE_PAUSED, SL_STATE_OFF_MUTED):
                # Disabled / off states
                bg = '#444'
                # Play states
            else:
                bg = '#090'
            self.pos_canvas[loop]['canvas'].coords(
                self.pos_canvas[loop]['border'], 2, 2, self.pos_canvas[loop]['canvas'].winfo_width() - 2, self.row_height - 2)
            if loop == self.selected_loop:
                self.pos_canvas[loop]['canvas'].itemconfigure(
                    self.pos_canvas[loop]['border'], state=tkinter.NORMAL)
            else:
                self.pos_canvas[loop]['canvas'].itemconfigure(
                    self.pos_canvas[loop]['border'], state=tkinter.HIDDEN)
            x = 0
            if len:
                x = int(
                    pos / len * self.pos_canvas[loop]['canvas'].winfo_width())
            self.pos_canvas[loop]['canvas'].coords(
                self.pos_canvas[loop]['line'], x, 0, x, self.row_height)
            self.pos_canvas[loop]['canvas'].configure(bg=bg)
            self.pos_canvas[loop]['canvas'].itemconfigure(self.pos_canvas[loop]['label'], text='{}/{} {}'.format(
                f'{pos:.1f}'.zfill(4), f'{len:.1f}'.zfill(4), zynthian_engine_sooperlooper.SL_STATES[state]['name']))
            if waiting and (next_state in (SL_STATE_MUTED, SL_STATE_OFF_MUTED) or state in (SL_STATE_MUTED, SL_STATE_OFF_MUTED)):
                if self.flash_count > 3:
                    self.pos_canvas[loop]['mute']['bg'] = self.BUTTON_ASSERTED
                else:
                    self.pos_canvas[loop]['mute']['bg'] = self.SLIDER_BG
            elif state in (SL_STATE_MUTED, SL_STATE_OFF_MUTED):
                self.pos_canvas[loop]['mute']['bg'] = self.BUTTON_ASSERTED
            else:
                self.pos_canvas[loop]['mute']['bg'] = self.SLIDER_BG

        # Update selected loop's parameters
        try:
            # Update input meters - needs to looks smooth so rapid update
            self.input_level_canvas.coords(self.input_level_fg, 0, 0, int(
                self.width * self.monitors['in_peak_meter']), self.row_height)
            thresh_x = int(self.monitors['rec_thresh']
                           * self.input_level_canvas.winfo_width())
            self.input_level_canvas.coords(
                self.threshold_line, thresh_x, 0, thresh_x, self.row_height)
            x = int(self.monitors['dry'] * self.dry_canvas.winfo_width())
            self.dry_canvas.coords(self.dry_fg, 0, 0, x, self.row_height)
            x = int(self.monitors['wet'] * self.wet_canvas.winfo_width())
            self.wet_canvas.coords(self.wet_fg, 0, 0, x, self.row_height)
            x = int(self.monitors['feedback'] *
                    self.feedback_canvas.winfo_width())
            self.feedback_canvas.coords(
                self.feedback_fg, 0, 0, x, self.row_height)
            x = int(self.monitors['input_gain'] *
                    self.input_level_canvas.winfo_width())
            self.input_level_canvas.coords(
                self.in_gain_marker, x-self.tri_size, 0, x+self.tri_size, 0, x, self.tri_size)

            # Calculate direction of play
            x = int(self.monitors['rate_output'])
            if x < 0:
                self.buttons['reverse'].configure(
                    bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
            else:
                self.buttons['reverse'].configure(
                    bg=self.SLIDER_BG, highlightbackground=self.SLIDER_BG, activebackground=self.SLIDER_BG)

            # Update state indication - next_state != -1 indicates waiting for pending operation
            state = self.monitors['state']
            next_state = self.monitors['next_state']
            waiting = self.monitors['waiting']
            if state != self.state or self.selected_loop != self.monitors['selected_loop_num']:
                for b in self.buttons:
                    if b != 'reverse':
                        self.buttons[b].configure(
                            bg=self.SLIDER_BG, highlightbackground=self.SLIDER_BG, activebackground=self.SLIDER_BG)
                if state == SL_STATE_RECORDING:
                    self.buttons['record'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                elif state == SL_STATE_OVERDUBBING:
                    self.buttons['overdub'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                elif state == SL_STATE_MULTIPLYING:
                    self.buttons['multiply'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                elif state == SL_STATE_INSERTING:
                    self.buttons['insert'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                elif state == SL_STATE_REPLACING:
                    self.buttons['replace'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                elif state == SL_STATE_PLAYING_ONCE:
                    self.buttons['oneshot'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                elif state == SL_STATE_SUBSTITUTING:
                    self.buttons['substitute'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                    self.buttons['substitute'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                elif state == SL_STATE_PAUSED:
                    self.buttons['pause'].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                self.state = state
                self.selected_loop = int(self.monitors['selected_loop_num'])
            if waiting or state in (SL_STATE_REC_STARTING, SL_STATE_REC_STOPPING):
                if state in (SL_STATE_REC_STARTING, SL_STATE_RECORDING, SL_STATE_REC_STOPPING) or next_state == SL_STATE_RECORDING:
                    btn = 'record'
                elif state == SL_STATE_OVERDUBBING or next_state == SL_STATE_OVERDUBBING:
                    btn = 'overdub'
                elif state == SL_STATE_MULTIPLYING or next_state == SL_STATE_MULTIPLYING:
                    btn = 'multiply'
                elif state == SL_STATE_INSERTING or next_state == SL_STATE_INSERTING:
                    btn = 'insert'
                elif state == SL_STATE_REPLACING or next_state == SL_STATE_REPLACING:
                    btn = 'replace'
                elif state == SL_STATE_PLAYING_ONCE or next_state == SL_STATE_PLAYING_ONCE:
                    btn = 'oneshot'
                elif state == SL_STATE_SUBSTITUTING or next_state == SL_STATE_SUBSTITUTING:
                    btn = 'substitute'
                elif state == SL_STATE_PAUSED or next_state == SL_STATE_PAUSED:
                    btn = 'pause'
                else:
                    return
                if self.flash_count > 3:
                    self.buttons[btn].configure(
                        bg=self.BUTTON_ASSERTED, highlightbackground=self.BUTTON_ASSERTED, activebackground=self.BUTTON_ASSERTED)
                else:
                    self.buttons[btn].configure(
                        bg=self.SLIDER_BG, highlightbackground=self.SLIDER_BG, activebackground=self.SLIDER_BG)

            # Check of request to remove a loop
            if 'loop_del' in self.monitors:
                self.processor.engine.monitors_dict.pop('loop_del')
                self.zyngui.show_confirm("Remove loop {}?".format(
                    self.selected_loop + 1), self.remove_loop)
                # TODO: This probably removes selected loop rather than last loop which might be expected behaviour

        # except KeyError:
            # logging.debug("KeyError ignored")
        except Exception as e:
            logging.warning(e)

    # ---------------------------------------------------------------------------
    # CUIA & LEDs methods
    # ---------------------------------------------------------------------------

    # Buttons => 'record', 'overdub', 'multiply', 'replace', 'substitute', 'insert', 'undo', 'redo', 'trigger', 'oneshot', 'reverse', 'pause'

    def cuia_toggle_record(self, params=None):
        if self.zyngui.alt_mode:
            state = self.monitors['state']
            if state in (SL_STATE_REC_STARTING, SL_STATE_RECORDING, SL_STATE_REC_STOPPING):
                btn = "record"
            elif state in (SL_STATE_PLAYING, SL_STATE_OVERDUBBING):
                btn = "overdub"
            elif state == SL_STATE_MULTIPLYING:
                btn = "multiply"
            elif state == SL_STATE_INSERTING:
                btn = "insert"
            elif state == SL_STATE_REPLACING:
                btn = "replace"
            else:
                btn = "record"
            self.processor.controllers_dict[btn].toggle()
            return True

    def cuia_stop(self, params=None):
        if self.zyngui.alt_mode:
            state = self.monitors['state']
            self.processor.controllers_dict['multiply'].toggle()
            return True

    def cuia_toggle_play(self, params=None):
        if self.zyngui.alt_mode:
            state = self.monitors['state']
            if state == SL_STATE_MUTED:
                self.processor.controllers_dict['mute'].set_value(0, True)
            elif state in (SL_STATE_PLAYING, SL_STATE_TRIGGER_PLAY, SL_STATE_PLAYING_ONCE):
                self.processor.controllers_dict['mute'].set_value(1, True)
            if state == SL_STATE_PAUSED:
                self.processor.controllers_dict['pause'].set_value(0, True)
            return True

    def cuia_arrow_up(self, params=None):
        if self.zyngui.alt_mode:
            self.processor.engine.prev_loop()
            return True

    def cuia_arrow_down(self, params=None):
        if self.zyngui.alt_mode:
            self.processor.engine.next_loop()
            return True

    def cuia_arrow_left(self, params=None):
        if self.zyngui.alt_mode:
            self.processor.engine.undo()
            return True

    def cuia_arrow_right(self, params=None):
        if self.zyngui.alt_mode:
            self.processor.engine.redo()
            return True

    def cuia_program_change(self, params=None):
        if self.zyngui.alt_mode:
            if len(params) > 0:
                pgm = int(params[0])
                if pgm == 5:
                    self.processor.controllers_dict['replace'].toggle()
                elif pgm == 6:
                    self.processor.controllers_dict['substitute'].toggle()
                elif pgm == 7:
                    self.processor.controllers_dict['insert'].toggle()
                elif pgm == 8:
                    self.processor.controllers_dict['loop_count'].nudge(1)
            return True

    def update_wsleds(self, leds):
        # ALT mode only!
        if not self.zyngui.alt_mode:
            return
        wsl = self.zyngui.wsleds
        color_default = wsl.wscolor_active2
        state = self.monitors['state']
        next_state = self.monitors['next_state']
        waiting = self.monitors['waiting']
        # logging.debug(f"STATE: {state}, NEXT: {next_state}, WAITING: {waiting}")

        # ALT button
        wsl.set_led(leds[0], color_default)

        # REC Button
        if state in (SL_STATE_REC_STARTING, SL_STATE_REC_STOPPING) or next_state in (SL_STATE_RECORDING,
                                                                                     SL_STATE_OVERDUBBING, SL_STATE_MULTIPLYING, SL_STATE_INSERTING, SL_STATE_REPLACING):
            wsl.blink(leds[1], wsl.wscolor_red)
        elif state in (SL_STATE_RECORDING, SL_STATE_OVERDUBBING, SL_STATE_MULTIPLYING, SL_STATE_INSERTING,
                       SL_STATE_REPLACING):
            if next_state == 'SL_STATE_PLAYING':
                wsl.blink(leds[1], wsl.wscolor_red)
            else:
                wsl.set_led(leds[1], wsl.wscolor_red)
        else:
            wsl.set_led(leds[1], color_default)
        # STOP button
        if next_state == SL_STATE_MULTIPLYING:
            wsl.blink(leds[2], wsl.wscolor_red)
        elif state == SL_STATE_MULTIPLYING:
            wsl.set_led(leds[2], wsl.wscolor_red)
        else:
            wsl.set_led(leds[2], color_default)
        # PLAY button:
        if next_state in (SL_STATE_PAUSED, SL_STATE_MUTED, SL_STATE_TRIGGER_PLAY, SL_STATE_PLAYING_ONCE):
            wsl.blink(leds[3], wsl.wscolor_green)
        elif state in (SL_STATE_PLAYING, SL_STATE_OVERDUBBING, SL_STATE_MULTIPLYING, SL_STATE_INSERTING,
                       SL_STATE_REPLACING, SL_STATE_PLAYING_ONCE, SL_STATE_SUBSTITUTING):
            wsl.set_led(leds[3], wsl.wscolor_green)
        else:
            wsl.set_led(leds[3], color_default)

        # Arrows & F1-F4
        for i in (4, 5, 6, 7, 10, 11, 12, 13):
            wsl.set_led(leds[i], color_default)

# *******************************************************************************
