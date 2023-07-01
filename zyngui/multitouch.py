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

"""A multitouch event"""
TouchEvent = namedtuple('TouchEvent', ('timestamp', 'type', 'code', 'value'))

# Touch event types
TS_IDLE = -1
TS_RELEASE = 0
TS_PRESS = 1
TS_MOVE = 2

# Drag modes
DRAG_HOROZONTAL = 1
DRAG_VERTICAL = 2
ZOOM_HORIZONTAL = 3
ZOOM_VERTICAL = 4

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
        
        self._id = -1 # Id for associated press/move events (same action/session)
        self._type = TS_IDLE # Current event type
            
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
        """Get id of event collection - press, move, release associated with same session"""

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
                self._type = TS_RELEASE
                return -1
            else:
                self._type = TS_PRESS
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

        # Event callback functions
        self._on_move = None
        self._on_press = None
        self._on_release = None
        self._on_drag_horizontal = None
        self._on_drag_vertical = None
        self._on_zoom_horizontal = None
        self._on_zoom_vertical = None

        self.device = self._detect_device(device)
        if self.device:
            try:
                self._f_device = open(self.device, 'rb', self.EVENT_SIZE)
            except:
                self._f_device = None
        else:
            self._f_device = None
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
        """Run outstanding press/release/move events"""

        for event in self.events:
            if event._type == TS_MOVE:
                if callable(self._on_move):
                    self._on_move(event)
            elif event._type == TS_PRESS:
                if callable(self._on_press):
                    self._on_press(event)
                event._type = TS_MOVE
            elif event._type == TS_RELEASE:
                if callable(self._on_release):
                    self._on_release(event)
                event._id = -1
                event._type = TS_IDLE
            self.process_gesture(event)

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
                        self._current_touch.x = self.max_x - event.value
                    else:
                        self._current_touch.x = event.value
                    if self._current_touch not in self.events:
                        self.events.append(self._current_touch)
                elif event.code == ecodes.ABS_MT_POSITION_Y:
                    if self._invert_y:
                        self._current_touch.y = self.max_y - event.value
                    else:
                        self._current_touch.y = event.value
                    if self._current_touch not in self.events:
                        self.events.append(self._current_touch)
    
    def process_gesture(self, event):
        """Process recent events into gestures"""

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

            if event._type == TS_MOVE and dtime > 0.2:
                delta_x = abs(self.touches[0].x - self.touches[1].x)
                delta_y = abs(self.touches[0].y - self.touches[1].y)
                deltadelta_x = delta_x - self._gesture_start_delta_x
                deltadelta_y = delta_y - self._gesture_start_delta_y
                if self._gesture_drag_axis is None:
                    if abs(deltadelta_x) > 40:
                        self._gesture_drag_axis = ZOOM_HORIZONTAL
                    elif abs(deltadelta_y) > 40:
                        self._gesture_drag_axis = ZOOM_VERTICAL
                    elif abs(self.touches[0].x - self._gesture_start_origin[0][0]) > 10 and deltadelta_x < 10:
                        self._gesture_drag_axis = DRAG_HOROZONTAL
                    elif abs(self.touches[0].y - self._gesture_start_origin[0][1]) > 10 and deltadelta_x < 10:
                        self._gesture_drag_axis = DRAG_VERTICAL
                elif self._gesture_drag_axis == DRAG_HOROZONTAL:
                    if self._on_drag_horizontal:
                        self._on_drag_horizontal(self.touches[0].x - self._gesture_start_origin[0][0])
                elif self._gesture_drag_axis == DRAG_VERTICAL:
                    if self._on_drag_vertical:
                        self._on_drag_vertical(self.touches[0].y - self._gesture_start_origin[0][1])
                elif self._gesture_drag_axis == ZOOM_HORIZONTAL:
                    if self._on_zoom_horizontal:
                        self._on_zoom_horizontal(deltadelta_x)
                elif self._gesture_drag_axis == ZOOM_VERTICAL:
                    if self._on_zoom_vertical:
                        self._on_zoom_vertical(deltadelta_y)
                """
                delta_x = self.touches[0].x - self.touches[1].x
                delta_y = self.touches[0].y - self.touches[1].y
                if abs(delta_x) > abs(delta_y):
                    delta = delta_x
                else:
                    delta = delta_y
                delta_delta = delta - self._gesture_last_delta
                if delta_delta > 1:
                    logging.warning("Pinch+")
                elif delta_delta < 1:
                    logging.warning("Pinch-")
                self._gesture_last_delta = delta
                """
        else:
            self._gesture_drag_axis = None
            self._gesture_press_start_time = 0
        self._gesture_last_held_count = self.touch_count

    def _detect_device(self, device):
        """Detect / validate multitouch device
        
        device - Path to device, e.g. /dev/input/event0. May be None to detect first valid file
        returns - Device path or None if invalid / none found
        """
        
        if device:
            devices = [device]
        else:
            devices = glob("/dev/input/event*")
        for device in devices:
            try:
                if ecodes.ABS_MT_SLOT in InputDevice(device).capabilities()[ecodes.EV_ABS][ecodes.ABS_Z]:
                    self.max_x = InputDevice(device).capabilities()[ecodes.EV_ABS][ecodes.ABS_X][1].max
                    self.max_y = InputDevice(device).capabilities()[ecodes.EV_ABS][ecodes.ABS_Y][1].max
                    return device
            except:
                pass
        return None
    
    def set_callback(self, event_type, cb):
        """Set event callback
        
        event_type - Name of event type ["press" | "release" | "move"]
        cb - Python function to call when event occurs
        """
        
        try:
            fn = getattr(self, f"set_{event_type}_callback", None)
            fn(cb)
        except:
            pass
    
    def set_press_callback(self, cb):
        """Set callback for press events
        
        cb - Python function to call when event occurs
        """
        
        self._on_press = cb
    
    def set_release_callback(self, cb):
        """Set callback for release events
        
        cb - Python function to call when event occurs
        """
        
        self._on_release = cb
    
    def set_move_callback(self, cb):
        """Set callback for move events
        
        cb - Python function to call when event occurs
        """
        
        self._on_move = cb
    
    def set_drag_horizontal_callback(self, cb):
        """Set callback for horizontal drag events
        
        cb - Python function to call when event occurs
        """
        
        self._on_drag_horizontal = cb
    
    def set_drag_vertical_callback(self, cb):
        """Set callback for vertical drag events
        
        cb - Python function to call when event occurs
        """
        
        self._on_drag_vertical = cb
    
    def set_zoom_horizontal_callback(self, cb):
        """Set callback for horizontal zoom events
        
        cb - Python function to call when event occurs
        """
        
        self._on_zoom_horizontal = cb
    
    def set_zoom_vertical_callback(self, cb):
        """Set callback for vertical zoom events
        
        cb - Python function to call when event occurs
        """
        
        self._on_zoom_vertical = cb
    
    def set_callbacks(self, cb):
        """Set single callback for all events
        
        cb - Python function to call when event occurs
        """
        self._on_press = cb
        self._on_release = cb
        self._on_move = cb
