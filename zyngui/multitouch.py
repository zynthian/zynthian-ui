# Based on code from https://github.com/pimoroni/python-multitouch

from glob import glob
import struct
from collections import namedtuple
from threading import Thread
from select import select
from queue import Queue
from evdev import ecodes, InputDevice
import logging
from time import monotonic
from dataclasses import dataclass
from subprocess import run,PIPE

from zyngui import zynthian_gui_config

"""A multitouch event"""
TouchEvent = namedtuple('TouchEvent', ('timestamp', 'type', 'code', 'value'))

# Touch event types
MTS_IDLE = -1
MTS_RELEASE = 0
MTS_PRESS = 1
MTS_MOTION = 2
TS_RELEASE = 3
TS_PRESS = 4
TS_MOTION = 5

# Drag modes
DRAG_HORIZONTAL = 1
DRAG_VERTICAL = 2
PINCH_HORIZONTAL = 3
PINCH_VERTICAL = 4

"""Class representing a touch slot (one slot per touch point)"""
class Touch(object):
    
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

        self._id = -1 # Id for associated press/motion events (same action/session)
        self._type = MTS_IDLE # Current event type
        self._handled = False # True if event session handled by multitouch event handler
        
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
                if self._type in [MTS_PRESS, MTS_MOTION]:
                    self._type = MTS_RELEASE
                    return -1
                else:
                    self._type = TS_RELEASE
            else:
                self._type = MTS_PRESS
                self._id = id
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

        self._running = False # True when thread is running
        self._thread = None # Background thread processing touch events
        self._invert_x = invert_x_axis
        self._invert_y = invert_y_axis
        self.events = [] # List of pending multipoint events (not yet sent)

        # Event callback functions - lists of TouchCallback objects
        self._on_motion = []
        self._on_press = [] 
        self._on_release = []
        self._on_drag_horizontal_begin = None
        self._on_drag_horizontal = None
        self._on_drag_horizontal_end = None
        self._on_drag_vertical_begin = None
        self._on_drag_vertical = None
        self._on_drag_vertical_end = None
        self._on_pinch_horizontal_begin = None
        self._on_pinch_horizontal = None
        self._on_pinch_horizontal_end = None
        self._on_pinch_vertical_begin = None
        self._on_pinch_vertical = None
        self._on_pinch_vertical_end = None

        self._f_device = None
        if device:
            devices = [device]
        else:
            devices = glob("/dev/input/event*")
        for device in devices:
            try:
                idev = InputDevice(device)
                if ecodes.ABS_MT_SLOT in idev.capabilities()[ecodes.EV_ABS][ecodes.ABS_Z]:
                    self.max_x = InputDevice(device).capabilities()[ecodes.EV_ABS][ecodes.ABS_X][1].max
                    self.max_y = InputDevice(device).capabilities()[ecodes.EV_ABS][ecodes.ABS_Y][1].max
                    self._f_device = open(device, 'rb', self.EVENT_SIZE)
                    for libinput in self.xinput("--list").split("\n"):
                        if idev.name in libinput and "slave  pointer" in libinput:
                            device_id = libinput.split("id=")[1].split()[0]
                            self.xinput("disable", device_id)
                            break
                    break
            except:
                pass


        self.touches = [Touch(x) for x in range(10)] # 10 touch slot objects
        self._event_queue = Queue() # Used to store evdev events before processing into touch events
        self._current_touch = self.touches[0] # Current touch object being processed
        
        # Gesture variables
        self._gesture_pinch_axis = None
        self._gesture_drag_axis = None
        self._gesture_last_delta = 0
        self._gesture_press_start_time = 0
        self._gesture_last_held_count = 0
        self._gesture_start_origin = [(0,0), (0,0)]
        
        self.touch_count = 0 # Quantity of currently pressed slots
        if self._f_device:
            self._thread = Thread(target=self._run, name="multitouch")
            self._thread.start()
    
    def _run(self):
        """Background (thread) event process"""
        self._running = True
        while self._running:
            r,w,x = select([self._f_device],[],[])
            event = self._f_device.read(self.EVENT_SIZE)
            (tv_sec, tv_usec, type, code, value) = struct.unpack(self.EVENT_FORMAT, event)
            self._event_queue.put(TouchEvent(tv_sec + (tv_usec / 1000000), type, code, value))
            if type == ecodes.EV_SYN:
                self.process_events()
    
    def __enter__(self):
        """Provide multitouch object for 'with' commands"""

        return self
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        """Release resources when Multitouch object exits"""

        if self._thread:
            self._running = False
            self._thread.join()
            self._thread = None
        if self._f_device:
            self._f_device.close()

    def _handle_event(self):
        """Run outstanding press/release/motion events
        
        If event not handled by multitouch driver then a similar event is sent for normal handling
        This event will not have state (modifier / mouse button) set.
        """

        now = int(monotonic() * 1000)
        for event in self.events:
            event.x = event.x_root - event.offset_x
            event.y = event.y_root - event.offset_y
            if event._type == MTS_PRESS:
                #event.widget = zynthian_gui_config.zyngui.get_current_screen_obj().winfo_containing(event.x_root, event.y_root)
                event.widget = zynthian_gui_config.top.winfo_containing(event.x_root, event.y_root)
                event.offset_x = event.widget.winfo_rootx() #TODO: Is this offset from root or just parent?
                event.offset_y = event.widget.winfo_rooty()
                event.x = event.x_root - event.offset_x
                event.y = event.y_root - event.offset_y
                try:
                    event.tag = event.widget.find_overlapping(event.x, event.y, event.x, event.y)[0]
                except:
                    event.tag = None
                for ev_handler in self._on_press:
                    if ev_handler.widget == event.widget and ev_handler.tag == event.tag:
                        ev_handler.function(event)
                        event._type = MTS_MOTION
                if event._type == MTS_PRESS:
                    event._type = TS_MOTION
                    event.widget.event_generate("<ButtonPress-1>",
                        x=event.x,
                        y=event.y,
                        rootx=event.x_root,
                        rooty=event.y_root,
                        time=now)
            elif event._type == MTS_RELEASE:
                for ev_handler in self._on_release:
                    if ev_handler.widget == event.widget and ev_handler.tag == event.tag:
                        ev_handler.function(event)
                event._handled = False
                event._id = -1
                event._type = MTS_IDLE
            elif event._type == MTS_MOTION:
                for ev_handler in self._on_motion:
                    if ev_handler.widget == event.widget and ev_handler.tag == event.tag:
                        ev_handler.function(event)
            elif event._type == TS_RELEASE:
                event.widget.event_generate("<ButtonRelease-1>",
                    x=event.x,
                    y=event.y,
                    rootx=event.x_root,
                    rooty=event.y_root,
                    time=now)
                event._id = -1
                event._type = MTS_IDLE
            elif event._type == TS_MOTION:
                event.widget.event_generate("<B1-Motion>",
                    x=event.x,
                    y=event.y,
                    rootx=event.x_root,
                    rooty=event.y_root,
                    time=now)
            #self.process_gesture(event)

        self.events = []

    def process_events(self):
        """Process pending evdev events"""

        while not self._event_queue.empty():
            event = self._event_queue.get()
            self._event_queue.task_done()
            if event.type == ecodes.EV_SYN:
                self._handle_event()

            elif event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_MT_SLOT:
                    if event.value < 10:
                        self._current_touch = self.touches[event.value]
                elif event.code == ecodes.ABS_MT_TRACKING_ID:
                    self.touch_count += self._current_touch.set_id(event.value)
                    if self._current_touch not in self.events:
                        self.events.append(self._current_touch)
                elif event.code == ecodes.ABS_MT_POSITION_X:
                    if self._invert_x:
                        self._current_touch.x_root = self.max_x - event.value
                    else:
                        self._current_touch.x_root = event.value
                    if self._current_touch not in self.events:
                        self.events.append(self._current_touch)
                elif event.code == ecodes.ABS_MT_POSITION_Y:
                    if self._invert_y:
                        self._current_touch.y_root = self.max_y - event.value
                    else:
                        self._current_touch.y_root = event.value
                    if self._current_touch not in self.events:
                        self.events.append(self._current_touch)
    
    def process_gesture(self, event):
        """Process recent events into gestures"""

        # Pinch start, pinch change, pinch end

        now = monotonic()
        dtime = now - self._gesture_press_start_time
        if self.touch_count == 0 and dtime < 0.2:
            # Quick tap
            logging.warning("2 finger tap")
            self._gesture_press_start_time = 0

        if self.touch_count > 1:
            # Handle 2 finger gestures

            if self._gesture_last_held_count < 2:
                # Start to tap
                self._gesture_press_start_time = now
                self._gesture_start_origin[0] = (self.touches[0].x, self.touches[0].y)
                self._gesture_start_origin[1] = (self.touches[1].x, self.touches[1].y)
                self._gesture_start_delta_x = abs(self.touches[0].x - self.touches[1].x)
                self._gesture_start_delta_y = abs(self.touches[0].y - self.touches[1].y)

            if event._type == TS_MOTION and dtime > 0.2:
                delta_x = abs(self.touches[0].x - self.touches[1].x)
                delta_y = abs(self.touches[0].y - self.touches[1].y)
                deltadelta_x = delta_x - self._gesture_start_delta_x
                deltadelta_y = delta_y - self._gesture_start_delta_y
                if self._gesture_drag_axis is None:
                    if abs(deltadelta_x) > 40:
                        self._gesture_drag_axis = PINCH_HORIZONTAL
                        if self._on_pinch_horizontal_begin:
                            self._on_pinch_horizontal_begin()
                    elif abs(deltadelta_y) > 40:
                        self._gesture_drag_axis = PINCH_VERTICAL
                        if self._on_pinch_vertical_begin:
                            self._on_pinch_vertical_begin()
                    elif abs(self.touches[0].x - self._gesture_start_origin[0][0]) > 10 and deltadelta_x < 10:
                        self._gesture_drag_axis = DRAG_HORIZONTAL
                        if self._on_drag_horizontal_begin:
                            self._on_drag_horizontal_begin()
                    elif abs(self.touches[0].y - self._gesture_start_origin[0][1]) > 10 and deltadelta_x < 10:
                        self._gesture_drag_axis = DRAG_VERTICAL
                        if self._on_drag_vertical_begin:
                            self._on_drag_vertical_begin()
                elif self._gesture_drag_axis == DRAG_HORIZONTAL:
                    if self._on_drag_horizontal:
                        self._on_drag_horizontal(self.touches[0].x - self._gesture_start_origin[0][0])
                elif self._gesture_drag_axis == DRAG_VERTICAL:
                    if self._on_drag_vertical:
                        self._on_drag_vertical(self.touches[0].y - self._gesture_start_origin[0][1])
                elif self._gesture_drag_axis == PINCH_HORIZONTAL:
                    if self._on_pinch_horizontal:
                        self._on_pinch_horizontal(deltadelta_x)
                elif self._gesture_drag_axis == PINCH_VERTICAL:
                    if self._on_pinch_vertical:
                        self._on_pinch_vertical(deltadelta_y)
        else:
            if self._gesture_drag_axis == PINCH_HORIZONTAL and self._on_pinch_horizontal_end:
                self._on_pinch_horizontal_end()
            elif self._gesture_drag_axis == PINCH_VERTICAL and self._on_pinch_vertical_end:
                self._on_pinch_vertical_end()
            elif self._gesture_drag_axis == DRAG_HORIZONTAL and self._on_drag_horizontal_end:
                self._on_drag_horizontal_end()
            elif self._gesture_drag_axis == DRAG_VERTICAL and self._on_drag_vertical_end:
                self._on_drag_vertical_end()

            self._gesture_drag_axis = None
            self._gesture_press_start_time = 0
        self._gesture_last_held_count = self.touch_count
    
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
    
