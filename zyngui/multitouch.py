#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Touchscreen Calibration Class
#
# Copyright (C) 2023 Brian Walton <brian@riban.co.uk>
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

# Based on code from https://github.com/pimoroni/python-multitouch

import struct
import logging
from enum import Enum
from glob import glob
from queue import Queue
from select import select
from time import monotonic
from threading import Thread
from subprocess import run, PIPE
from dataclasses import dataclass
from collections import namedtuple
from evdev import ecodes, InputDevice

from zyngui import zynthian_gui_config

"""A multitouch event"""
TouchEvent = namedtuple('TouchEvent', ('timestamp', 'type', 'code', 'value'))


class MultitouchTypes(Enum):
    # Touch event types
    IDLE = 0
    MULTI_RELEASE = 1
    MULTI_PRESS = 2
    MULTI_MOTION = 3
    SINGLE_RELEASE = 11
    SINGLE_PRESS = 12
    SINGLE_MOTION = 13
    GESTURE_PRESS = 21
    GESTURE_RELEASE = 22
    GESTURE_MOTION = 23
    GESTURE_H_DRAG = 24
    GESTURE_V_DRAG = 25
    GESTURE_H_PINCH = 26
    GESTURE_V_PINCH = 27


class Touch(object):
    """Class representing a touch slot (one slot per touch point)"""

    def __init__(self, slot):
        """Instantiate a Touch object
        slot - Touch point slot index
        """

        self.slot = slot

        self._x = None
        self._y = None
        self.last_x = None
        self.last_y = None
        self.offset_x = 0
        self.offset_y = 0
        self.start_x = None
        self.start_y = None

        # Id for associated press/motion events (same action/session)
        self._id = -1
        self._type = MultitouchTypes.IDLE  # Current event type

    @property
    def position(self):
        """Current position of touch event  as tuple (x,y)"""

        return (self.x, self.y)

    @property
    def last_position(self):
        """Position of previous touch event as tuple (x,y)
        (-1,-1) if this is the first event after instatiation
        """

        return (self.last_x, self.last_y)

    @property
    def id(self):
        """Get id of event collection - press, motion, release associated with same session"""

        return self._id

    @property
    def type(self):
        """Get event type"""

        return self._type

    def set_id(self, id):
        """Set event tracking identifier
        id - Event id
        """

        if id != self._id:
            if id == -1:
                # event state has changed to RELEASE
                if self._type in [MultitouchTypes.MULTI_PRESS, MultitouchTypes.MULTI_MOTION]:
                    self._type = MultitouchTypes.MULTI_RELEASE
                    return -1
                elif self._type.value >= MultitouchTypes.GESTURE_PRESS.value:
                    self._type = MultitouchTypes.GESTURE_RELEASE
                else:
                    self._type = MultitouchTypes.SINGLE_RELEASE
            else:
                self._type = MultitouchTypes.MULTI_PRESS
                self._id = id
                self.start_x = self.x
                self.start_y = self.y
                return 1
        return 0

    @property
    def x(self):
        """Get event x coordinate"""

        return self._x

    @x.setter
    def x(self, value):
        """Set event x coordinate"""

        if self._x is None:
            self.last_x = value
        else:
            self.last_x = self._x
        self._x = value

    @property
    def y(self):
        """Get event y coordinate"""

        return self._y

    @y.setter
    def y(self, value):
        """Set event y coordinate"""

        if self._y is None:
            self.last_y = value
        else:
            self.last_y = self._y
        self._y = value


@dataclass
class TouchCallback:
    widget: object
    tag: int
    function: object


class MultiTouch(object):
    """Class representing a multitouch interface driver"""

    EVENT_FORMAT = str('llHHi')
    EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

    def __init__(self, device=None, invert_x_axis=False, invert_y_axis=False):
        """Instantiate the touch driver

        Creates an instance of the driver attached to the first multitouch hardware discovered or using the specified device.

        device - Path to the device, e.g. /dev/input/event0 (optional)
        invert_x_axis - True to invert x axis (optional)
        invert_y_axis - True to invert y axis (optional)
        """

        self._running = False  # True when thread is running
        self.thread = None  # Background thread processing touch events
        self._invert_x = invert_x_axis
        self._invert_y = invert_y_axis
        self.events = []  # List of pending multipoint events (not yet sent)
        self.gesture_events = []  # List of events currently active as gestures
        self._g_pending = None  # Event that is pending multiple touch gesture start
        self._g_timeout = None  # Timer used to detect multiple touch gesture start

        # Event callback functions - lists of TouchCallback objects
        self._on_motion = []
        self._on_press = []
        self._on_release = []
        self._on_gesture = []

        self._f_device = None
        if device:
            devices = [device]
        else:
            devices = glob("/dev/input/event*")
        for device in devices:
            try:
                idev = InputDevice(device)
                idev_caps = idev.capabilities()
                # Look for the first device supporting multi-touch
                if idev_caps[ecodes.EV_ABS][ecodes.ABS_Z][0] == ecodes.ABS_MT_SLOT:
                    self.max_x = idev_caps[ecodes.EV_ABS][ecodes.ABS_X][1].max
                    self.max_y = idev_caps[ecodes.EV_ABS][ecodes.ABS_Y][1].max
                    self._f_device = open(device, 'rb', self.EVENT_SIZE)
                    for libinput in self.xinput("--list").split("\n"):
                        if idev.name in libinput and "slave  pointer" in libinput:
                            device_id = libinput.split("id=")[1].split()[0]
                            self.xinput("disable", device_id)
                            break
                    break
            except:
                pass

        self.touches = [Touch(x) for x in range(10)]  # 10 touch slot objects
        # Used to store evdev events before processing into touch events
        self._evdev_event_queue = Queue()
        # Current touch object being processed
        self._current_touch = self.touches[0]

        self.touch_count = 0  # Quantity of currently pressed slots
        if self._f_device:
            self.thread = Thread(target=self._run, name="Multitouch")
            self.thread.start()

    def _run(self):
        """Background (thread) event process"""
        self._running = True
        while self._running:
            r, w, x = select([self._f_device], [], [], 1)
            if r and r[0]:
                event = self._f_device.read(self.EVENT_SIZE)
                (tv_sec, tv_usec, type, code, value) = struct.unpack(
                    self.EVENT_FORMAT, event)
                self._evdev_event_queue.put(TouchEvent(
                    tv_sec + (tv_usec / 1000000), type, code, value))
                if type == ecodes.EV_SYN:
                    self._process_evdev_events()

    def __enter__(self):
        """Provide multitouch object for 'with' commands"""

        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Release resources when Multitouch object exits"""
        self.stop()

    def stop(self):
        if self.thread:
            self._running = False
            self.thread.join()
            self.thread = None
        if self._f_device:
            self._f_device.close()
        self._f_device = None

    def _process_evdev_events(self):
        """Process pending evdev events"""

        while not self._evdev_event_queue.empty():
            evdev_event = self._evdev_event_queue.get()
            self._evdev_event_queue.task_done()
            if evdev_event.type == ecodes.EV_SYN:
                self._process_touch_events()

            elif evdev_event.type == ecodes.EV_ABS:
                if evdev_event.code == ecodes.ABS_MT_SLOT:
                    if evdev_event.value < 10:
                        self._current_touch = self.touches[evdev_event.value]
                elif evdev_event.code == ecodes.ABS_MT_TRACKING_ID:
                    self.touch_count += self._current_touch.set_id(
                        evdev_event.value)
                    if self._current_touch not in self.events:
                        self.events.append(self._current_touch)
                elif evdev_event.code == ecodes.ABS_MT_POSITION_X:
                    if self._invert_x:
                        self._current_touch.x_root = self.max_x - evdev_event.value
                    else:
                        self._current_touch.x_root = evdev_event.value
                    if self._current_touch not in self.events:
                        self.events.append(self._current_touch)
                elif evdev_event.code == ecodes.ABS_MT_POSITION_Y:
                    if self._invert_y:
                        self._current_touch.y_root = self.max_y - evdev_event.value
                    else:
                        self._current_touch.y_root = evdev_event.value
                    if self._current_touch not in self.events:
                        self.events.append(self._current_touch)

    def _process_touch_events(self):
        """Run outstanding press/release/motion events

        If event not handled by multitouch driver then a similar event is sent for normal handling
        This event will not have state (modifier / mouse button) set.
        """

        now = int(monotonic() * 1000)
        for event in self.events:
            try:
                event.x = event.x_root - event.offset_x
                event.y = event.y_root - event.offset_y
            except Exception as e:
                # Sometimes root attirbutes are not set / available
                logging.warning(e)
                continue
            event.time = now

            if event._type == MultitouchTypes.MULTI_PRESS:
                event.widget = zynthian_gui_config.top.winfo_containing(
                    event.x_root, event.y_root)
                event.offset_x = event.widget.winfo_rootx()
                event.offset_y = event.widget.winfo_rooty()
                event.x = event.x_root - event.offset_x  # Reassert because offset has changed
                event.y = event.y_root - event.offset_y
                event.last_x = event.x
                event.last_y = event.y

                if self._g_pending:
                    # There is an existing touch event pending gesture detection
                    if self._on_gesture_start(event):
                        # Gesture detection identified a valid gesture binding so do not process as individual touch event
                        continue
                else:
                    # First touch so wait to see if another touch event arrives to start a gesture
                    event._type = MultitouchTypes.GESTURE_PRESS
                    self._g_pending = event
                    self._g_timeout = zynthian_gui_config.top.after(
                        100, self._on_touch_timeout)

            elif event._type == MultitouchTypes.MULTI_RELEASE:
                if self._g_pending:
                    # Cancel multitouch detection and send on_press event before processing release event
                    self._on_touch_timeout(False)
                for ev_handler in self._on_release:
                    if ev_handler.widget == event.widget and ev_handler.tag == event.tag:
                        ev_handler.function(event)
                event._id = -1
                event._type = MultitouchTypes.IDLE

            elif event._type == MultitouchTypes.MULTI_MOTION:
                if self._g_pending:
                    # Cancel multitouch detection and send on_press event before processing motion event
                    self._on_touch_timeout(False)
                for ev_handler in self._on_motion:
                    if ev_handler.widget == event.widget and ev_handler.tag == event.tag:
                        ev_handler.function(event)

            elif event._type == MultitouchTypes.GESTURE_MOTION:
                dx1 = event.x - event.start_x
                dx2 = event.gest_pair.x - event.gest_pair.start_x
                dy1 = event.y - event.start_y
                dy2 = event.gest_pair.y - event.gest_pair.start_y
                if abs(dx1) > 2 and abs(dx2) > 2:
                    if dx1 ^ dx2 < 0:
                        event._type = event.gest_pair._type = MultitouchTypes.GESTURE_H_PINCH
                    else:
                        event._type = event.gest_pair._type = MultitouchTypes.GESTURE_H_DRAG
                elif abs(dy1) > 2 and abs(dy2) > 2:
                    if dy1 ^ dy2 < 0:
                        event._type = event.gest_pair._type = MultitouchTypes.GESTURE_V_PINCH
                    else:
                        event._type = event.gest_pair._type = MultitouchTypes.GESTURE_V_DRAG

            elif event._type == MultitouchTypes.GESTURE_RELEASE:
                if self._g_pending:
                    # Cancel multitouch detection and send on_press event before processing release event
                    event._type = MultitouchTypes.GESTURE_PRESS
                    self._on_touch_timeout(True)
                    if event.widget:
                        event.widget.event_generate("<ButtonRelease-1>",
                                                    x=event.x,
                                                    y=event.y,
                                                    rootx=event.x_root,
                                                    rooty=event.y_root,
                                                    time=now)
                else:
                    for ev_handler in self._on_release:
                        if ev_handler.widget == event.widget and ev_handler.tag == event.tag:
                            ev_handler.function(event)

                if hasattr(event, "gest_pair"):
                    event2 = event.gest_pair
                    event2._id = -1
                    event2._type = MultitouchTypes.IDLE
                    if hasattr(event2, "gest_pair"):
                        delattr(event2, "gest_pair")
                    delattr(event, "gest_pair")
                event._id = -1
                event._type = MultitouchTypes.IDLE

            elif event._type == MultitouchTypes.GESTURE_H_PINCH:
                pinch = abs(event.x - event.gest_pair.x) - \
                    abs(event.last_x - event.gest_pair.last_x)
                # logging.warning(f"H-pinch {pinch}")
                for ev_handler in self._on_gesture:
                    if ev_handler.widget == None or ev_handler.widget == event.widget:
                        ev_handler.function(
                            MultitouchTypes.GESTURE_H_PINCH, pinch)

            elif event._type == MultitouchTypes.GESTURE_V_PINCH:
                pinch = abs(event.y - event.gest_pair.y) - \
                    abs(event.last_y - event.gest_pair.last_y)
                # logging.warning(f"V-pinch {pinch}")
                for ev_handler in self._on_gesture:
                    if ev_handler.widget == None or ev_handler.widget == event.widget:
                        ev_handler.function(
                            MultitouchTypes.GESTURE_V_PINCH, pinch)

            elif event._type == MultitouchTypes.GESTURE_H_DRAG:
                if event.slot > event.gest_pair.slot:
                    drag = event.x - event.last_x
                    # logging.warning(f"H-drag {drag}")
                    for ev_handler in self._on_gesture:
                        if ev_handler.widget == None or ev_handler.widget == event.widget:
                            ev_handler.function(
                                MultitouchTypes.GESTURE_H_DRAG, drag)

            elif event._type == MultitouchTypes.GESTURE_V_DRAG:
                if event.slot > event.gest_pair.slot:
                    drag = event.y - event.last_y
                    # logging.warning(f"V-drag {drag}")
                    for ev_handler in self._on_gesture:
                        if ev_handler.widget == None or ev_handler.widget == event.widget:
                            ev_handler.function(
                                MultitouchTypes.GESTURE_V_DRAG, drag)

            elif event._type == MultitouchTypes.SINGLE_RELEASE:
                if event.widget:
                    event.widget.event_generate("<ButtonRelease-1>",
                                                x=event.x,
                                                y=event.y,
                                                rootx=event.x_root,
                                                rooty=event.y_root,
                                                time=now)
                    event._id = -1
                    event._type = MultitouchTypes.IDLE

            elif event._type == MultitouchTypes.SINGLE_MOTION:
                if event.widget:
                    event.widget.event_generate("<B1-Motion>",
                                                x=event.x,
                                                y=event.y,
                                                rootx=event.x_root,
                                                rooty=event.y_root,
                                                time=now)

        self.events = []

    def _on_touch_timeout(self, try_single_touch=True):
        """Handle timeout of initial touch when no other touch event has occured, i.e. no gesture"""

        zynthian_gui_config.top.after_cancel(self._g_timeout)
        if self._g_pending is None:
            return
        event = self._g_pending
        self._g_pending = None
        try:
            event.tag = event.widget.find_overlapping(
                event.x, event.y, event.x, event.y)[0]
        except:
            event.tag = None
        for ev_handler in self._on_press:
            if ev_handler.widget == event.widget and ev_handler.tag == event.tag:
                ev_handler.function(event)
                event._type = MultitouchTypes.MULTI_MOTION
        if try_single_touch and event._type == MultitouchTypes.GESTURE_PRESS and event.widget:
            event._type = MultitouchTypes.SINGLE_MOTION
            event.widget.event_generate("<ButtonPress-1>",
                                        x=event.x,
                                        y=event.y,
                                        rootx=event.x_root,
                                        rooty=event.y_root,
                                        time=event.time)

    def _on_gesture_start(self, event):
        """Handle 2 finger press as start of gesture"""

        zynthian_gui_config.top.after_cancel(self._g_timeout)
        # logging.warning(f"Gesture start ({self._g_pending.x}.{self._g_pending.y}) ({event.x},{event.y})")
        if event == self._g_pending:
            logging.warning("Gesture detected same event!!!")
            return True  # TODO: This shouldn't be possible
        for ev_handler in self._on_gesture:
            if ev_handler.widget is None or ev_handler.widget == self._g_pending.widget:
                event._type = self._g_pending._type = MultitouchTypes.GESTURE_MOTION
                self._g_pending.gest_pair = event
                event.gest_pair = self._g_pending
                # Set start points again in case of movement before second touch
                self._g_pending.start_x = self._g_pending.x
                self._g_pending.start_y = self._g_pending.y
                event.start_x = event.x
                event.start_y = event.y
                self._g_pending = None
                return True
        event._id = -1
        event._type = MultitouchTypes.IDLE
        self._on_touch_timeout(False)
        return False

    def xinput(self, *args):
        """Run xinput
        args: List of arguments to pass to xinput
        Returns: Output of xinput as string
        Credit: https://github.com/reinderien/xcalibrate
        """
        try:
            return run(args=('/usr/bin/xinput', *args),
                       stdout=PIPE, check=True,
                       universal_newlines=True).stdout
        except:
            return ""

    def tag_bind(self, widget, tagOrId, sequence, function, add=False):
        """Binds events to canvas objects

        widget - Canvas widget
        tagOrId - Tag or object ID to bind event to
        sequence - Event sequence to bind ["press" "motion" | "release" | "horizontal_drag"]
        function - Callback function
        add - True to append the binding otherwise remove existing bindings (default)

        Note that the bindings are applied to items that have this tag at the time of the tag_bind method call.
        If tags are later removed from those items, the bindings will persist on those items. 
        If the tag you specify is later applied to items that did not have that tag when you called tag_bind, that binding will not be applied to the newly tagged items.
        """

        event_list = getattr(self, f"_on_{sequence}", None)
        if isinstance(event_list, list) and callable(function):
            existing = []
            if tagOrId is None:
                tags = [None]
            else:
                tags = widget.find_withtag(tagOrId)
            for tag in tags:
                for event in event_list:
                    if event.widget == widget and tag == event.tag:
                        existing.append(event)

            if not add:
                for event in existing:
                    event_list.remove(event)

            for tag in tags:
                event_list.append(TouchCallback(widget, tag, function))

    def tag_unbind(self, widget, tagOrId, sequence, function=None):
        """Remove binding of press event

        widget - Canvas widget
        tagOrId - Tag or object ID to bind event to
        sequence - Event sequence to bind ["press" "motion" | "release" | "horizontal_drag"]
        function - Callback function (Optional - default None=remove all bindings)
        """

        event_list = getattr(self, f"_on_{sequence}", None)
        if event_list:
            existing = []
            tags = widget.find_withtag(tagOrId)
            for tag in tags:
                for event in event_list:
                    if function:
                        if event.widget == widget and tag == event.tag and function == event.function:
                            existing.append(event)
                    else:
                        if event.widget == widget and tag == event.tag:
                            existing.append(event)

            for event in existing:
                event_list.remove(event)

    def set_drag_horizontal_begin_callback(self, cb):
        """Set callback for horizontal drag begin event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_drag_horizontal_begin = cb

    def set_drag_horizontal_callback(self, cb):
        """Set callback for horizontal drag event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_drag_horizontal = cb

    def set_drag_horizontal_end_callback(self, cb):
        """Set callback for horizontal drag end event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_drag_horizontal_end = cb

    def set_drag_vertical_begin_callback(self, cb):
        """Set callback for vertical drag begin event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_drag_vertical_begin = cb

    def set_drag_vertical_callback(self, cb):
        """Set callback for vertical drag events

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_drag_vertical = cb

    def set_drag_vertical_end_callback(self, cb):
        """Set callback for vertical drag end event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_drag_vertical_end = cb

    def set_pinch_horizontal_begin_callback(self, cb):
        """Set callback for horizontal pinch begin event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_pinch_horizontal_begin = cb

    def set_pinch_horizontal_callback(self, cb):
        """Set callback for horizontal pinch event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_pinch_horizontal = cb

    def set_pinch_horizontal_end_callback(self, cb):
        """Set callback for horizontal pinch end event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_pinch_horizontal_end = cb

    def set_pinch_vertical_begin_callback(self, cb):
        """Set callback for vertical pinch begin event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_pinch_vertical_begin = cb

    def set_pinch_vertical_callback(self, cb):
        """Set callback for vertical pinch event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_pinch_vertical = cb

    def set_pinch_vertical_end_callback(self, cb):
        """Set callback for vertical pinch end event

        cb - Python function to call when event occurs
        """

        if callable(cb):
            self._on_pinch_vertical_end = cb
