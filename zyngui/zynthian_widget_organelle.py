# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Organelle OLED"
#
# Copyright (C) 2025 Ronald Summers <ronfsum@gmail.com>
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
# ******************************************************************************

import math
import liblo
import logging
import tkinter as tk

# Zynthian specific modules
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_widget_base import zynthian_widget_base
from zyngui.zynthian_gui_controller import zynthian_gui_controller

COLOR_PANEL = zynthian_gui_config.color_panel_bg
COLOR_TEXT = zynthian_gui_config.color_panel_tx
COLOR_OUTLINE = "#404040"
COLOR_BUTTON = "#B07000"
COLOR_BUTTON_LIGHT = "#00A000"
COLOR_KNOB = "#B07000"

ORGANELLE_OSC_PORT_IN = 3000
ORGANELLE_OSC_PORT_OUT = 3001

ORGANELLE_OLED_WIDTH = 128
ORGANELLE_OLED_HEIGHT = 64


class OscButton(tk.Canvas):
    """
    Custom touchable button that sends OSC messages when pressed.
    """

    def __init__(self, parent, diameter=70, osc_target=None, label="", osc_path="/button", **kwargs):
        super().__init__(parent, width=diameter, height=diameter, bg=COLOR_PANEL, highlightthickness=0, **kwargs)
        self.diameter = diameter
        self.osc_target = osc_target
        self.osc_path = osc_path

        # Draw the circular button.
        self.button = self.create_oval(2, 2, diameter - 2, diameter - 2, fill=COLOR_BUTTON, outline=COLOR_OUTLINE, width=2)
        # Place the label at the center.
        self.create_text(diameter // 2, diameter // 2, text=label, font=("Arial", 12), fill=COLOR_TEXT, anchor=tk.CENTER)

        # Bind press and release events.
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        """Handle button press: change color and send OSC 'press' message."""
        self.itemconfig(self.button, fill=COLOR_BUTTON_LIGHT)
        self.send_osc(1)

    def on_release(self, event):
        """Handle button release: revert color and send OSC 'release' message."""
        self.itemconfig(self.button, fill=COLOR_BUTTON)
        self.send_osc(0)

    def send_osc(self, value):
        """Send an OSC message with the specified value."""
        if self.osc_target:
            try:
                liblo.send(self.osc_target, self.osc_path, value)
            except Exception as e:
                logging.error(f"Error sending OSC message: {e}")


class LedIndicator(tk.Canvas):
    """
    LED indicator widget controlled via OSC messages.
    """
    COLORS = {
        0: "black", 1: "red", 2: "green", 3: "blue",
        4: "yellow", 5: "purple", 6: "cyan", 7: "white"
    }

    def __init__(self, parent, diameter=15, osc_target=None, **kwargs):
        super().__init__(parent, width=diameter, height=diameter, bg=COLOR_PANEL, highlightthickness=0, **kwargs)
        self.osc_target = osc_target
        self.led = self.create_oval(2, 2, diameter - 2, diameter - 2, fill=self.COLORS[0], outline=COLOR_OUTLINE, width=1)
        self.current_state = 0

    def set_state(self, state):
        """
        Set the LED state (color) based on an integer value (0-7).
        """
        try:
            self.current_state = max(min(0, int(state)), 7)
            self.itemconfig(self.led, fill=self.COLORS[self.current_state])
            return True
        except ValueError:
            logging.error(f"Invalid LED state value: {state}")
        return False


class VolumeSlider(tk.Frame):
    """
    Vertical volume slider widget that sends OSC messages on value change.
    """

    def __init__(self, parent, zyngui_control=None, width=200, height=60, **kwargs):
        super().__init__(parent, bg=COLOR_PANEL, **kwargs)
        self.zyngui_control = zyngui_control
        # Create and pack the slider.
        self.slider = tk.Scale(self, to=100, from_=0, resolution=1, orient=tk.HORIZONTAL,
            length=width, width=int(0.7 * height), sliderlength=width//8, showvalue=True,
            bg=COLOR_PANEL, fg=COLOR_TEXT, highlightthickness=0, troughcolor=zynthian_gui_config.color_bg,
            command=self.on_value_change)
        self.slider.pack(side="top", pady=0)
        # Create and pack the label.
        self.label = tk.Label(self, text="VOLUME", bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Arial", height//3))
        self.label.pack(side="bottom", pady=0)
        # Set initial value
        self.slider.set(70)
        self.on_value_change(70)

    def on_value_change(self, value):
        """
        Handle slider value changes by sending an OSC volume message.
        """
        try:
            zctrl_volume = self.zyngui_control.screen_processor.controllers_dict['volume']
            zctrl_volume.set_value(zctrl_volume.value_max * float(value) / 100.0)
            #liblo.send(self.osc_target, "/vol", float(vol))
        except Exception as e:
            #logging.error(f"Error sending OSC volume message: {e}")
            logging.error(f"Can't set volume zctrl value {value}: {e}")

    def get_value(self):
        """Return the current slider value."""
        return self.slider.get()

    def set_value(self, value):
        """Set the slider to the specified value."""
        self.slider.set(value)

    def refresh_value(self):
        """refresh the slider value from engine zctrl."""
        try:
            zctrl_volume = self.zyngui_control.screen_processor.controllers_dict['volume']
            self.slider.set(100.0 * zctrl_volume.value / zctrl_volume.value_max)
        except Exception as e:
            logging.error(f"Can't get volume zctrl => {e}")


class MarkedEncoder(tk.Canvas):
    """
    Marked encoder knob with tick marks and a rotating pointer indicator.
    """

    def __init__(self, parent, diameter=120, osc_target=None, label="ENC", **kwargs):
        super().__init__(parent, width=diameter, height=diameter,
                         bg=COLOR_PANEL, highlightthickness=0, **kwargs)
        self.diameter = diameter
        self.osc_target = osc_target
        self.rotation_steps = 4  # Quantized OSC events
        self.last_step = 0

        # Define rotation limits (in radians).
        self.min_angle = 0
        self.max_angle = (360 * math.pi) / 180

        self.current_angle = 0
        self.prev_angle = 0
        self.at_min_limit = False
        self.at_max_limit = False

        # Draw the knob base.
        self.knob = self.create_oval(2, 2, diameter - 2, diameter - 2, fill=COLOR_KNOB, outline=COLOR_OUTLINE, width=2)

        self.draw_tick_marks()

        # Draw pointer indicator (initially pointing upward).
        center = self.diameter / 2
        pointer_length = self.diameter / 2 - 2
        self.pointer = self.create_line(center, center, center, center - pointer_length, fill=COLOR_TEXT, width=8)

        # Draw center circle for aesthetics.
        self.create_oval(
            center - diameter / 3.75, center - diameter / 3.75,
            center + diameter / 3.75, center + diameter / 3.75,
            fill=COLOR_OUTLINE, outline=COLOR_KNOB, width=1
        )

        # Add label below the knob.
        self.create_text(center, center, text=label, font=("Arial", 12), fill=COLOR_TEXT, anchor=tk.CENTER)

        # Bind events for interaction.
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.is_pressed = False

    def draw_tick_marks(self):
        """Draw tick marks around the knob edge."""
        center = self.diameter / 2
        outer_radius = self.diameter / 2
        inner_radius = outer_radius - 6  # Tick length
        num_ticks = 16
        for i in range(num_ticks):
            angle = 2 * math.pi * i / num_ticks
            x1 = center + inner_radius * math.cos(angle)
            y1 = center + inner_radius * math.sin(angle)
            x2 = center + outer_radius * math.cos(angle)
            y2 = center + outer_radius * math.sin(angle)
            self.create_line(x1, y1, x2, y2, fill=COLOR_TEXT, width=2)

    def on_press(self, event):
        """
        Handle press event. If the center is pressed, send an encoder select message.
        """
        self.is_pressed = True
        center = self.diameter / 2
        center_radius = self.diameter / 5
        distance = math.hypot(event.x - center, event.y - center)
        if distance <= center_radius and self.osc_target:
            try:
                liblo.send(self.osc_target, "/enc_sel", 1)
                self.after(100, lambda: liblo.send(self.osc_target, "/enc_sel", 0))
            except Exception as e:
                logging.error(f"Error sending OSC message: {e}")

    def on_drag(self, event):
        """
        Handle drag events by updating the pointer based on the drag angle
        and sending quantized OSC rotation events.
        """
        if not self.is_pressed:
            return

        center = self.diameter / 2
        raw_angle = math.atan2(event.y - center, event.x - center)
        angle = raw_angle if raw_angle >= 0 else raw_angle + 2 * math.pi

        self.prev_angle = self.current_angle

        # Check for boundary crossing.
        crossing_clockwise = self.prev_angle > 1.5 * math.pi and angle < 0.5 * math.pi
        crossing_counterclockwise = self.prev_angle < 0.5 * math.pi and angle > 1.5 * math.pi

        rotating_clockwise = crossing_clockwise or (angle > self.prev_angle and not crossing_counterclockwise)
        rotating_counterclockwise = crossing_counterclockwise or (angle < self.prev_angle and not crossing_clockwise)

        # Apply rotation limits.
        if rotating_clockwise and (angle < self.min_angle or
                                   (self.prev_angle >= self.max_angle and angle <= self.min_angle + 0.5)):
            angle = self.max_angle
            self.at_max_limit = True
        elif rotating_counterclockwise and angle > self.max_angle and self.prev_angle <= self.min_angle + 0.5:
            angle = self.min_angle
            self.at_min_limit = True
        elif rotating_clockwise and angle > self.max_angle:
            angle = self.max_angle
            self.at_max_limit = True
        elif rotating_counterclockwise and angle < self.min_angle:
            angle = self.min_angle
            self.at_min_limit = True
        else:
            self.at_min_limit = False
            self.at_max_limit = False

        self.current_angle = angle

        # Update pointer indicator.
        pointer_length = self.diameter / 2 - 2
        end_x = center + pointer_length * math.cos(angle)
        end_y = center + pointer_length * math.sin(angle)
        self.coords(self.pointer, center, center, end_x, end_y)

        # Quantize angle into steps and send OSC events if step changes.
        #new_step = int(angle / (3.8 * math.pi) * self.rotation_steps) % self.rotation_steps
        new_step = int(angle / (2 * math.pi) * self.rotation_steps) % self.rotation_steps

        if new_step != self.last_step and self.osc_target:
            try:
                if rotating_clockwise and not self.at_max_limit:
                    liblo.send(self.osc_target, "/enc_down", 1)
                    self.after(50, lambda: liblo.send(self.osc_target, "/enc_down", 0))
                elif rotating_counterclockwise and not self.at_min_limit:
                    liblo.send(self.osc_target, "/enc_up", 1)
                    self.after(50, lambda: liblo.send(self.osc_target, "/enc_up", 0))
            except Exception as e:
                logging.error(f"Error sending OSC message: {e}")
            self.last_step = new_step

    def on_release(self, event):
        """Reset flags when the pointer is released."""
        self.is_pressed = False
        self.at_min_limit = False
        self.at_max_limit = False


class zynthian_widget_organelle(zynthian_widget_base):
    """
    Main widget class for the Organelle OLED display.
    Combines an OLED display, volume slider, control buttons, and encoder.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.configure(background=COLOR_PANEL)

        self.zyngui = zynthian_gui_config.zyngui
        self.zyngui_control = self.zyngui.screens['control']
        self.shown = False

        # Oled plot & update
        self.update_pending = False
        self.last_flip_time = 0
        self.batch_updates = True
        self.batch_update_after = 16  # ms (aim for ~60 fps)
        self.line_items = {}          # key: y (int), value: canvas item ID for printed text
        self.inverted_lines = {}      # key: y (int), value: Boolean (True if highlighted)
        self.line_bboxes = {}         # Cached bounding boxes for text lines
        self.pending_batch = []       # List of pending canvas operations
        self.text_items_by_position = {}  # Map text items by (x, y) position

        # Navigation state.
        self.current_page_index = 0
        self.in_parameter_view = False
        self.select_mode = False
        self.aux_pushed = False

        # Initialize OSC client.
        try:
            self.osc_target = liblo.Address("localhost", ORGANELLE_OSC_PORT_OUT)
        except liblo.AddressError as err:
            logging.error(f"OSC client initialization error: {err}")
            self.osc_target = None

        # Start OSC server for display.
        self.server = liblo.ServerThread(ORGANELLE_OSC_PORT_IN)
        self.setup_osc_handlers()
        self.server.start()

        # Calculate widget geometry
        layout = self.zyngui_control.layout
        try:
            self.width = int((1.0 - layout['ctrl_width'] * (layout['columns'] - 1)) * self.zyngui_control.width)
            self.height = self.zyngui_control.height - zynthian_gui_config.topbar_height
            logging.debug(f"Widget Size => {self.width} x {self.height}")
        except Exception as e:
            logging.warning(f"Can't calculate widget geometry => {e}")
            self.width = 240
            self.height = 300

        # Configure layout depending on hardware
        if zynthian_gui_config.check_wiring_layout(["V5"]):
            self.show_touch_widgets = False
            self.switch_i_selmode = 19
            self.switch_i_aux = 23
        elif zynthian_gui_config.check_wiring_layout(["Z2"]):
            self.show_touch_widgets = False
            self.switch_i_selmode = 9
            self.switch_i_aux = 10
        elif zynthian_gui_config.check_kit_version(["V4"]):
            self.show_touch_widgets = False
            self.switch_i_selmode = 5
            self.switch_i_aux = 4
        else:
            self.show_touch_widgets = True
            self.switch_i_selmode = None
            self.switch_i_aux = None

        #self.show_touch_widgets = True
        if layout['columns'] == 2:
            if self.show_touch_widgets:
                self.wunit = int(0.015 * self.width)
                self.hunit = int(0.015 * self.height)
            else:
                self.wunit = int(0.020 * self.width)
                self.hunit = int(0.020 * self.height)
        else:
            self.wunit = int(0.035 * self.width)
            self.hunit = int(0.025 * self.height)

        # OLED display settings.
        # Scaling factor for all components in OLED
        self.oled_scale = self.width // ORGANELLE_OLED_WIDTH
        if self.oled_scale > 4 and float(self.oled_scale * ORGANELLE_OLED_WIDTH) / self.width > 0.95:
            self.oled_scale -= 1
        self.oled_width = self.oled_scale * ORGANELLE_OLED_WIDTH
        self.oled_height = self.oled_scale * ORGANELLE_OLED_HEIGHT
        logging.debug(f"OLED scale = {self.oled_scale} => {self.oled_width} x {self.oled_height}")

        if self.show_touch_widgets:
            padx = (self.width - self.oled_width) // 2
            pady = (self.width - self.oled_width) // 6
        else:
            padx = (self.width - self.oled_width) // 2
            pady = (self.width - self.oled_width) // 3

        # Top container: holds OLED display and volume slider.
        self.top_container = tk.Frame(self, bg=COLOR_PANEL)
        self.top_container.pack(pady=0, padx=0)

        # OLED display container.
        self.display_frame = tk.Frame(self.top_container, bg=COLOR_PANEL, padx=padx, pady=pady)
        self.display_frame.pack(side="left")
        self.canvas = tk.Canvas(self.display_frame, width=self.oled_width, height=self.oled_height,
                                bg=zynthian_gui_config.color_bg, takefocus=0)
        self.canvas.pack()
        self.bg_rect = self.canvas.create_rectangle(0, 0, self.oled_width, self.oled_height, fill="", width=0)
        self.canvas.tag_bind(self.bg_rect, "<ButtonPress-1>", self.on_canvas_touch)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_touch, add="+")

        # Controls frame.
        self.controls_frame = tk.Frame(self, bg=COLOR_PANEL)
        self.controls_frame.pack(expand=True, fill='both', padx=padx, pady=0)

        # LED indicator and control buttons.
        if self.show_touch_widgets:
            self.volume_slider = VolumeSlider(self.controls_frame, zyngui_control=self.zyngui_control, width=self.width, height=6*self.hunit)
            self.volume_slider.pack(side="top", padx=0, pady=0)
            self.aux_button = OscButton(self.controls_frame, diameter=6 * self.wunit, osc_target=self.osc_target, label="AUX", osc_path="/aux")
            self.aux_button.pack(side="left", padx=self.wunit)
            self.fs_button = OscButton(self.controls_frame, diameter=6 * self.wunit, osc_target=self.osc_target, label="FS", osc_path="/fs")
            self.encoder = MarkedEncoder(self.controls_frame, diameter=8 * self.wunit, osc_target=self.osc_target, label="ENC")
        else:
            self.volume_slider = None

        self.led_indicator = LedIndicator(self.controls_frame, diameter=2*self.wunit, osc_target=self.osc_target)
        self.led_indicator.pack(side="left", padx=self.wunit)

        # Organelle selector zctrl
        self.zselector_ctrl = zynthian_controller(None, "Select", {'labels': ['<>']})
        self.zselector_gui = None

    def setup_osc_handlers(self):
        """Register OSC handlers for various message paths."""
        self.osc_handlers = {
            "/oled/gFlip": self.handle_gFlip,
            "/oled/gCleanln": self.handle_gCleanln,
            "/oled/gClear": self.handle_gClear,
            "/oled/gSetPixel": self.handle_gSetPixel,
            "/oled/gLine": self.handle_gLine,
            "/oled/gBox": self.handle_gBox,
            "/oled/gFillArea": self.handle_gFillArea,
            "/oled/gCircle": self.handle_gCircle,
            "/oled/gFilledCircle": self.handle_gFilledCircle,
            "/oled/gPrintln": self.handle_gPrintln,
            "/oled/gInvertArea": self.handle_gInvertArea,
            "/oled/ginvertLine": self.handle_ginvertLine,
            "/led": self.handle_led,
            "/enc_up": self.handle_enc_up,
            "/enc_down": self.handle_enc_down,
            "/enc_sel": self.handle_enc_sel
        }
        for path, handler in self.osc_handlers.items():
            self.server.add_method(path, None, handler)
        self.server.add_method(None, None, self.fallback_handler)

    def handle_led(self, path, args):
        #logging.debug(f"Received OSC LED message: {path} {args}")
        if args:
            state = int(args[0])
            self.led_indicator.set_state(state)

    def handle_enc_up(self, path, args):
        if args and args[0] == 1:
            if self.in_parameter_view:
                self.return_to_menu('up')
            elif self.osc_target:
                liblo.send(self.osc_target, "/enc_up", 1)

    def handle_enc_down(self, path, args):
        if args and args[0] == 1:
            if self.in_parameter_view:
                self.return_to_menu('down')
            elif self.osc_target:
                liblo.send(self.osc_target, "/enc_down", 1)

    def handle_enc_sel(self, path, args):
        if args and args[0] == 1:
            self.in_parameter_view = True
            if self.osc_target:
                liblo.send(self.osc_target, "/enc_sel", 1)

    def return_to_menu(self, direction):
        """
        Change the menu page based on the encoder direction.
        """
        self.in_parameter_view = False
        sorted_keys = sorted(self.line_items.keys())
        max_index = len(sorted_keys) - 1 if sorted_keys else 4

        if direction == 'up':
            new_index = max(0, self.current_page_index - 1)
        elif direction == 'down':
            new_index = min(max_index, self.current_page_index + 1)
        else:
            new_index = self.current_page_index

        self.current_page_index = new_index
        self.handle_ginvertLine("/ginvertLine", [new_index])

    def fallback_handler(self, path, args):
        logging.debug(f"Fallback OSC message: {path} {args}")

    def schedule_update(self):
        """
        Schedule a batched canvas update if not already pending.
        """
        if not self.update_pending and self.batch_updates:
            self.update_pending = True
            self.after(self.batch_update_after, self.perform_update)

    def perform_update(self):
        """Perform all batched canvas operations and refresh the canvas."""
        self.update_pending = False
        if self.pending_batch:
            for op, args, kwargs in self.pending_batch:
                op(*args, **kwargs)
            self.pending_batch = []
        self.canvas.update_idletasks()
        self.canvas.update()

    def add_to_batch(self, operation, *args, **kwargs):
        """
        Add an operation to the batch queue or execute immediately if batching is disabled.
        """
        if self.batch_updates:
            self.pending_batch.append((operation, args, kwargs))
            self.schedule_update()
        else:
            operation(*args, **kwargs)

    def handle_gFlip(self, path, args):
        #logging.debug(f"Received OSC: {path} {args}")
        if not self.batch_updates:
            self.canvas.update_idletasks()
            self.canvas.update()
        else:
            self.schedule_update()

    def handle_gCleanln(self, path, args):
        logging.debug(f"Received OSC gCleanln: {path} {args}")
        if len(args) < 1:
            logging.error(f"gCleanln message received with insufficient arguments: {args}")
            return
        try:
            n = int(args[0])
        except Exception:
            logging.error(f"Invalid argument for gCleanln: {args}")
            return

        fill_params = {
            1: [0, 0, 8, 128, 9, 0],
            2: [0, 0, 20, 128, 9, 0],
            3: [0, 0, 32, 128, 9, 0],
            4: [0, 0, 44, 128, 9, 0],
            5: [0, 0, 54, 128, 10, 0]
        }
        if n in fill_params:
            self.handle_gFillArea(path, fill_params[n])
        else:
            logging.error(f"gCleanln received an invalid line number: {n}")

    def handle_gClear(self, path, args):
        logging.debug(f"Received OSC: {path} {args}")
        self.in_parameter_view = False

        def clear_canvas():
            self.canvas.delete("all")
            self.line_items.clear()
            self.inverted_lines.clear()
            self.line_bboxes.clear()
            self.text_items_by_position = {}

        self.add_to_batch(clear_canvas)

    def handle_gLine(self, path, args):
        logging.debug(f"Received OSC: {path} {args}")
        mode, x1, y1, x2, y2, color = args
        x1, y1 = int(x1 * self.oled_scale) + 2, int(y1 * self.oled_scale) + 6
        x2, y2 = int(x2 * self.oled_scale) + 2, int(y2 * self.oled_scale) + 6
        fill_color = "white" if int(color) == 1 else "black"

        def draw_line():
            self.canvas.create_line(x1, y1, x2, y2, fill=fill_color, width=self.oled_scale)

        self.add_to_batch(draw_line)

    def handle_gSetPixel(self, path, args):
        logging.debug(f"Received OSC: {path} {args}")
        dummy, x, y, c = args
        x, y = int(x * self.oled_scale), int(y * self.oled_scale)
        fill_color = "white" if int(c) == 1 else "black"

        def draw_pixel():
            self.canvas.create_rectangle(x, y, x + self.oled_scale, y + self.oled_scale, fill=fill_color, outline=fill_color)

        self.add_to_batch(draw_pixel)

    def handle_gBox(self, path, args):
        logging.debug(f"Received OSC: {path} {args}")
        if len(args) >= 6:
            mode, x, y, w, h, color = args[:6]
            woffset = self.oled_scale - 1
            x = int(x * self.oled_scale) + woffset
            y = int(y * self.oled_scale) + woffset
            w = int(w * self.oled_scale) - woffset
            h = int(h * self.oled_scale) - woffset
            outline_color = "white" if int(color) == 1 else "black"

            def draw_box():
                self.canvas.create_rectangle(x, y, x + w, y + h, outline=outline_color, width=self.oled_scale, fill="")

            self.add_to_batch(draw_box)
        else:
            logging.error(f"gBox message received with insufficient arguments: {args}")

    def handle_gFillArea(self, path, args):
        #logging.debug(f"Received OSC: {path} {args}")
        if len(args) >= 6:
            mode, x, y, w, h, color = args[:6]
            woffset = self.oled_scale - 1
            x = int(x * self.oled_scale) + woffset
            y = int(y * self.oled_scale) + woffset
            w = int(w * self.oled_scale) - woffset
            h = int(h * self.oled_scale) - woffset
            fill_color = 'black' if int(color) == 0 else 'white'

            def draw_filled_area():
                self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill_color, outline=fill_color)

            self.add_to_batch(draw_filled_area)
        else:
            logging.error(f"gFillArea message received with insufficient arguments: {args}")

    def handle_gCircle(self, path, args):
        logging.debug(f"Received OSC: {path} {args}")
        mode, x, y, r, color = args
        woffset = self.oled_scale - 1
        x = int(x * self.oled_scale) + woffset
        y = int(y * self.oled_scale) + woffset
        r = int(r * self.oled_scale) - woffset
        outline_color = "white" if int(color) == 1 else "black"

        def draw_circle():
            self.canvas.create_oval(x - r, y - r, x + r, y + r, outline=outline_color, width=self.oled_scale, fill="")

        self.add_to_batch(draw_circle)

    def handle_gFilledCircle(self, path, args):
        logging.debug(f"Received OSC: {path} {args}")
        mode, x, y, r, color = args
        woffset = self.oled_scale - 1
        x = int(x * self.oled_scale) + woffset
        y = int(y * self.oled_scale) + woffset
        r = int(r * self.oled_scale) - woffset
        outline_color = "white" if int(color) == 1 else "black"

        def draw_filled_circle():
            self.canvas.create_oval(x - r, y - r, x + r, y + r, outline=outline_color, fill=outline_color, width=self.oled_scale)

        self.add_to_batch(draw_filled_circle)

    def handle_gPrintln(self, path, args):
        logging.debug(f"Received OSC gPrintln - {len(args)} args: {args}")
        if len(args) < 5:
            logging.error(f"gPrintln message received with insufficient arguments: {args}")
            return
        mode, x, y, font_size, color = args[:5]
        try:
            text_words = args[5:]
        except:
            text_words = []
        try:
            x_unscaled = int(x)
            y_unscaled = int(y) - 1
        except ValueError:
            return
        x_scaled = x_unscaled * self.oled_scale
        y_scaled = y_unscaled * self.oled_scale
        try:
            fs = int(0.95 * font_size) * self.oled_scale
        except Exception:
            fs = 8 * self.oled_scale
        if fs > 16:
            #font_family = "TkFixedFont"
            font_family = "FreeMonoBold"
        else:
            font_family = "FreeMono"
        text = " ".join(map(str, text_words)).strip()
        if not text:
            return
        fill_color = "white" if int(color) == 1 else "black"
        tag = f"line_{x_unscaled}_{y_unscaled}"
        y_tag = f"y_{y_unscaled}"

        def draw_text():
            self.canvas.delete(tag)
            text_id = self.canvas.create_text(x_scaled, y_scaled,
                anchor='nw', text=text, fill=fill_color,
                font=(font_family, fs), tags=[tag, y_tag]
            )
            self.text_items_by_position[(x_unscaled, y_unscaled)] = text_id
            if x_unscaled <= 10:
                self.line_items[y_unscaled] = text_id
                self.line_bboxes[y_unscaled] = self.canvas.bbox(text_id)
            bbox = self.canvas.bbox(text_id)
            if bbox:
                touch_rect = self.canvas.create_rectangle(0, bbox[1], self.oled_width, bbox[3], fill="", outline="", tags=[tag])
                self.canvas.tag_lower(touch_rect, text_id)
                self.canvas.tag_bind(touch_rect, "<ButtonPress-1>", self.on_text_touch)
            self.canvas.tag_bind(text_id, "<ButtonPress-1>", self.on_text_touch)

        self.add_to_batch(draw_text)

    def handle_ginvertLine(self, path, args):
        logging.debug(f"Received OSC ginvertLine - {args}")
        if len(args) < 1:
            logging.error(f"ginvertLine message received with insufficient arguments: {args}")
            return
        try:
            page = int(args[0])
            self.current_page_index = page
        except Exception:
            logging.error(f"Invalid ginvertLine argument: {args}")
            return

        sorted_keys = sorted(self.line_items.keys())
        if not sorted_keys:
            logging.debug("No menu lines present to highlight")
            return
        page = max(0, min(page, len(sorted_keys) - 1))

        def update_highlights():
            self.canvas.delete("highlight")
            for key, text_id in self.line_items.items():
                if key == sorted_keys[page]:
                    bbox = self.canvas.bbox(text_id)
                    if bbox:
                        highlight = self.canvas.create_rectangle(
                            0, bbox[1] - 2, self.oled_width, bbox[3] + 2,
                            fill=zynthian_gui_config.color_ctrl_bg_on,
                            outline="", tags=["highlight"]
                        )
                        self.canvas.tag_lower(highlight, text_id)
                    self.canvas.itemconfig(text_id, fill=zynthian_gui_config.color_ctrl_tx)
                else:
                    self.canvas.itemconfig(text_id, fill=zynthian_gui_config.color_panel_tx)
        self.add_to_batch(update_highlights)

    def on_text_touch(self, event):
        """
        Handle touch selection of menu items by simulating encoder messages.
        """
        current_item = event.widget.find_withtag("current")
        if not current_item:
            return
        item = current_item[0]
        tags = event.widget.gettags(item)
        menu_tag = next((tag for tag in tags if tag.startswith("line_")), None)
        if not menu_tag:
            return
        parts = menu_tag.split("_")
        if len(parts) < 3:
            return
        try:
            y_unscaled = int(parts[2])
        except ValueError:
            return
        sorted_keys = sorted(self.line_items.keys())
        try:
            target_index = sorted_keys.index(y_unscaled)
        except ValueError:
            return

        diff = target_index - self.current_page_index
        if diff > 0:
            for i in range(diff):
                delay = 50 * i
                self.after(delay, lambda: liblo.send(self.osc_target, "/enc_down", 1))
                self.after(delay + 50, lambda: liblo.send(self.osc_target, "/enc_down", 0))
        elif diff < 0:
            for i in range(abs(diff)):
                delay = 50 * i
                self.after(delay, lambda: liblo.send(self.osc_target, "/enc_up", 1))
                self.after(delay + 50, lambda: liblo.send(self.osc_target, "/enc_up", 0))
        self.current_page_index = target_index
        total_delay = abs(diff) * 50 + 100
        self.after(total_delay, lambda: liblo.send(self.osc_target, "/enc_sel", 1))
        self.after(total_delay + 100, lambda: liblo.send(self.osc_target, "/enc_sel", 0))

    def select_page(self, page_index):
        """
        Force selection of a menu item by index.
        """
        self.current_page_index = page_index
        if self.osc_target:
            liblo.send(self.osc_target, "/enc_sel", 1)
            self.after(100, lambda: liblo.send(self.osc_target, "/enc_sel", 0))

    # Needs work.  Return to menu is not working properly
    def on_canvas_touch(self, event):
        """
        Handle OLED touch: simulate enc_down when not in menu view.
        """
        logging.debug("OLED touched in non-menu view; simulating enc_down")
        if self.in_parameter_view and self.osc_target:
            liblo.send(self.osc_target, "/enc_down", 1)
            self.after(50, lambda: liblo.send(self.osc_target, "/enc_down", 0))

    def handle_gInvertArea(self, path, args):
        logging.debug(f"Received OSC: {path} {args}")
        mode, x, y, w, h = args
        x, y = int(x * self.oled_scale), int(y * self.oled_scale)
        w, h = int(w * self.oled_scale), int(h * self.oled_scale)

        def invert_area():
            self.canvas.create_rectangle(x, y, x + w, y + h, fill='white')

        self.add_to_batch(invert_area)

    def show(self):
        """Display the widget."""
        if not self.shown:
            self.shown = True
        # Display or not FS widget
        if self.show_touch_widgets:
            if self.processor.engine.preset_config.get("organelle_fs_button", True):
                self.fs_button.pack(side="left", padx=self.wunit)
            else:
                self.fs_button.forget()
        # Display or not selector widget
        if self.processor.engine.preset_config.get("organelle_selector", True):
            self.selector = True
        else:
            self.selector = False
        if self.show_touch_widgets:
            if self.selector:
                self.encoder.pack(side="right", padx=self.wunit)
            else:
                self.encoder.forget()

    def hide(self):
        """Hide the widget."""
        if self.shown:
            self.shown = False

    def update(self):
        """Update the widget display if it is currently shown."""
        if self.shown and self.zyngui_control.shown:
            self.refresh_gui()

    def refresh_gui(self):
        """ Refresh the widget GUI """
        # Refresh the OLED canvas.
        if not self.update_pending:
            self.canvas.update()
        # Refresh the volume slider.
        if self.volume_slider:
            self.volume_slider.refresh_value()

    def zynpot_cb(self, i, dval):
        """Manage knobs => Only organelle selector """
        if self.osc_target:
            if self.select_mode and self.selector and i == 3:
                if dval > 0:
                    liblo.send(self.osc_target, f"/enc_down", 1)
                    self.after(50, lambda: liblo.send(self.osc_target, "/enc_down", 0))
                elif dval < 0:
                    liblo.send(self.osc_target, f"/enc_up", 1)
                    self.after(50, lambda: liblo.send(self.osc_target, "/enc_up", 0))
                return True
            #liblo.send(self.osc_target, f"/knob/{i}", dval)
            #return True
        return False

    def switch(self, i, t='S'):
        """Manage Organelle switches => Only selector """
        if self.selector and self.select_mode and i == 3:
            if t == 'S':
                liblo.send(self.osc_target, f"/enc_sel", 1)
                self.after(100, lambda: liblo.send(self.osc_target, "/enc_sel", 0))
                self.set_select_mode(False)
                return True
        elif self.selector and self.switch_i_selmode is not None and i == self.switch_i_selmode:
            if t == 'S' or t == 'B':
                self.switch_select_mode()
            return True
        elif self.switch_i_aux is not None and i == self.switch_i_aux:
            self.switch_aux(t)
            return True
        return False

    def switch_select_mode(self):
        if self.select_mode:
            self.set_select_mode(False)
            liblo.send(self.osc_target, f"/enc_sel", 1)
            self.after(100, lambda: liblo.send(self.osc_target, "/enc_sel", 0))
        else:
            self.set_select_mode(True)
            liblo.send(self.osc_target, "/enc_down", 1)
            self.after(50, lambda: liblo.send(self.osc_target, "/enc_down", 0))

    def switch_aux(self, t):
        if t == 'P':
            self.aux_pushed = True
            self.zyngui.zynswitch_disable_autolong()
            liblo.send(self.osc_target, "/aux", 1)
        else:
            self.aux_pushed = False
            self.zyngui.zynswitch_enable_autolong()
            liblo.send(self.osc_target, "/aux", 0)

    def set_select_mode(self, sm=True):
        self.select_mode = sm
        zgui_ctrls = self.zyngui_control.zgui_controllers
        layout = self.zyngui_control.layout
        if self.select_mode:
            # Hide controller widgets
            for i in range(0, len(zgui_ctrls)):
                if zgui_ctrls[i]:
                    zgui_ctrls[i].grid_remove()
            # Show selector widgets
            if self.zselector_gui:
                self.zselector_gui.config(self.zselector_ctrl)
                self.zselector_gui.show()
            else:
                self.zselector_gui = zynthian_gui_controller(zynthian_gui_config.select_ctrl,
                                                             self.zyngui_control.main_frame,
                                                             self.zselector_ctrl,
                                                             hidden=False,
                                                             selcounter=False,
                                                             orientation=layout['ctrl_orientation'])
            self.zselector_gui.grid(row=layout['ctrl_pos'][3][0], column=layout['ctrl_pos'][3][1], sticky="news")
        else:
            # Hide selector:
            self.zselector_gui.grid_remove()
            # Show controller widgets
            for i in range(0, len(zgui_ctrls)):
                if zgui_ctrls[i]:
                    zgui_ctrls[i].grid()

    # ---------------------------------------------------------------------------
    # CUIA & LEDs methods
    # ---------------------------------------------------------------------------

    def cuia_v5_zynpot_switch(self, params):
        return self.switch(params[0], params[1].upper())

    def cuia_arrow_up(self, params=None):
        if self.select_mode:
            self.zynpot_cb(3, -1)
            return True

    def cuia_arrow_down(self, params=None):
        if self.select_mode:
            self.zynpot_cb(3, 1)
            return True

    def update_wsleds(self, leds):
        # F3 & F4
        wsl = self.zyngui.wsleds
        if self.selector:
            if self.select_mode:
                #wsl.set_led(leds[12], wsl.wscolor_active2)
                wsl.blink(leds[12], wsl.wscolor_active2)
            else:
                wsl.set_led(leds[12], wsl.wscolor_active2)
        if self.aux_pushed:
            wsl.set_led(leds[13], wsl.wscolor_green)
        else:
            wsl.set_led(leds[13], wsl.wscolor_active2)

