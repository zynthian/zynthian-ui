import tkinter
import logging
from zyngui import zynthian_widget_base


class zynthian_widget_drawbar(zynthian_widget_base.zynthian_widget_base):
    DRAWBAR_SLOTS = 9
    DRAWBAR_POSITIONS = 9
    DRAWBAR_MAX = DRAWBAR_POSITIONS - 1
    DRAWBAR_Y_OFFSET = -2

    def __init__(self, parent):
        super().__init__(parent)
        base = self.rows
        self.rows = base // 2
        self.brown = 'dark red'
        self.white = '#fff'
        self.black = '#000'
        self.outline = 'wheat'
        self.border = 2
        self.drawbar_settings = [[self.brown, '16'],
                                 [self.brown, '5⅓'],
                                 [self.white, '8'],
                                 [self.white, '4'],
                                 [self.black, '2⅔'],
                                 [self.white, '2'],
                                 [self.black, '1⅗'],
                                 [self.black, '1⅓'],
                                 [self.white, '1']]

        self.drawbars = [None, None, None, None,
                         None, None, None, None,
                         None]

        self.widget_canvas = tkinter.Canvas(self,
                                            height=1,
                                            width=1,
                                            bd=0,
                                            highlightthickness=0,
                                            bg='#000'
                                            )
        self.drawbar_nums = {}
        self.drawbar_values = {}
        self.drag = {"item": None, "y": 0, 'barnum': None, 'value': None}
        self.widget_canvas.bind("<ButtonPress-1>", self.on_press)
        self.widget_canvas.bind("<B1-Motion>", self.on_motion)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_release)

    def _drawbar_ctrl(self, i):
        return self.processor.controllers_dict[self.drawbars[i]]

    def _drawbar_calibration(self, ctrl):
        # Ticks are interpolation knots, not snap values.
        if ctrl.ticks and len(ctrl.ticks) == self.DRAWBAR_POSITIONS:
            return [(i, ctrl.ticks[i]) for i in range(self.DRAWBAR_POSITIONS)]
        # Linear controls, e.g. Calf organ 0.0..8.0.
        return [(0, ctrl.value_min), (self.DRAWBAR_MAX, ctrl.value_max)]

    def _value_to_position(self, ctrl, value):
        points = self._drawbar_calibration(ctrl)
        first_value = points[0][1]
        last_value = points[-1][1]

        if last_value >= first_value:
            if value <= first_value:
                return 0.0
            if value >= last_value:
                return float(self.DRAWBAR_MAX)
        else:
            if value >= first_value:
                return 0.0
            if value <= last_value:
                return float(self.DRAWBAR_MAX)

        for (p0, v0), (p1, v1) in zip(points, points[1:]):
            if min(v0, v1) <= value <= max(v0, v1):
                if v0 == v1:
                    return float(p0)
                return p0 + (p1 - p0) * (value - v0) / (v1 - v0)

        return float(self.DRAWBAR_MAX)

    def _position_to_value(self, ctrl, position):
        position = max(0.0, min(float(self.DRAWBAR_MAX), position))
        points = self._drawbar_calibration(ctrl)

        for (p0, v0), (p1, v1) in zip(points, points[1:]):
            if p0 <= position <= p1:
                if p1 == p0:
                    return v0
                return v0 + (position - p0) * (v1 - v0) / (p1 - p0)

        return points[-1][1]

    def set_processor(self, processor):
        super().set_processor(processor)
        drawbar_ctrls = [k for k, v in self.processor.controllers_dict.items()
                         if hasattr(v, 'drawbar')]
        if (len(drawbar_ctrls) > 0):
            self.drawbars = drawbar_ctrls

    def show(self):
        super().show()

    def on_press(self, event):
        # the drag area under mouse, if any
        canvas = self.widget_canvas
        for item in reversed(canvas.find_overlapping(event.x, event.y,
                                                     event.x, event.y)):
            tags = self.widget_canvas.gettags(item)
            if "track" in tags:
                for tag in tags:
                    if tag.startswith('drag') and tag[4:].isdigit():
                        try:
                            barnum = int(tag[4:])
                            ctrl = self._drawbar_ctrl(barnum)
                            y = max(0, min(self.height, event.y))
                            self.drag.update(item=item, y=y,
                                             barnum=barnum, value=ctrl.value)
                        except Exception as e:
                            logging.error(e)
                        return

    def on_motion(self, event):
        if self.drag is not None and self.drag["item"]:
            ctrl = self._drawbar_ctrl(self.drag['barnum'])
            y = max(0, min(self.height, event.y))
            # Start from the position corresponding to the value when pressed,
            # then apply the pointer delta in position units.
            start_position = self._value_to_position(ctrl, self.drag['value'])
            delta_position = ((y - self.drag['y']) /
                              self.height) * self.DRAWBAR_MAX
            position = start_position + delta_position
            ctrl.set_value(self._position_to_value(ctrl, position))

    def on_release(self, event):
        self.drag["item"] = None

    def on_size(self, event):
        super().on_size(event)
        self.widget_canvas.delete("drawbar")
        for i in range(len(self.drawbars)):
            self.draw_drawbar(i)

    def refresh_gui(self):
        super().refresh_gui()
        canvas = self.widget_canvas
        canvas.pack(anchor=tkinter.CENTER, expand=False)
        for i in range(len(self.drawbars)):
            self.move_drawbar(i)

    def moveto_group(self, tag, y):
        # current top‑left of the group
        _, y1, _, _ = self.widget_canvas.bbox(tag)
        self.widget_canvas.move(tag, 0, y - y1)

    def draw_drawbar(self, i):
        canvas = self.widget_canvas
        tag = f"bar{i}"
        tags = (tag, "drawbar")
        width = (self.width - 2 * self.border) // max(self.DRAWBAR_SLOTS, len(self.drawbars))
        track = canvas.create_rectangle(0, 0, 0, 0,
                                        outline="#333", fill="#000",
                                        tags=(f"drag{i}", "track", "drawbar"))
        rect = canvas.create_rectangle(0, 0, 0, 0,
                                       outline=self.outline, fill="#000", tags=tags)
        step_height = self.height / self.DRAWBAR_POSITIONS

        color, text = self.drawbar_settings[i]

        try:
            # position / size drag area
            canvas.coords(track, self.border + i * width, -1,
                          self.border + ((i+1) * width), self.height + 1)
            # position / size drawbar
            canvas.coords(rect, self.border + 2 + i*width, self.DRAWBAR_Y_OFFSET,
                          self.border + ((i+1) * width) - 2, self.height + self.DRAWBAR_Y_OFFSET)
            # handle starts in the full-out position, at the bottom
            canvas.create_rectangle(self.border + i*width + 1,
                                    self.DRAWBAR_MAX * step_height + self.DRAWBAR_Y_OFFSET,
                                    self.border + ((i + 1) * width - 1),
                                    self.height + self.DRAWBAR_Y_OFFSET,
                                    outline=self.outline, fill=color,
                                    tags=(*tags, ))
            canvas.create_text((0.5 * width + self.border + 1 + (i * width),
                                (self.DRAWBAR_MAX + 0.5) * step_height + self.DRAWBAR_Y_OFFSET),
                               text=text,
                               fill=self.black if color == self.white else self.white,
                               tags=tags)
            nums = []
            for step in range(self.DRAWBAR_MAX):
                num = canvas.create_text((0.5 * width + self.border + 1 + (i * width),
                                          (step + 0.5) * step_height + self.DRAWBAR_Y_OFFSET),
                                         fill='grey', text=self.DRAWBAR_MAX - step, tags=tags)
                nums.append(num)
            self.drawbar_nums[i] = nums
            self.drawbar_values[i] = None  # Force redraw

        except Exception as e:
            logging.error(e)

    def move_drawbar(self, i):
        ctrl = self._drawbar_ctrl(i)
        value = ctrl.value
        if self.drawbar_values.get(i, None) == value:
            return
        self.drawbar_values[i] = value
        canvas = self.widget_canvas
        step_height = self.height / self.DRAWBAR_POSITIONS

        position = self._value_to_position(ctrl, value)
        try:
            # Full-in (position 0) at the top, full-out (position 8) at the bottom.
            self.moveto_group(f"bar{i}",
                              (position - self.DRAWBAR_MAX) * step_height + self.DRAWBAR_Y_OFFSET)
            number = round(position)
            for x, text in enumerate(self.drawbar_nums[i]):
                label_number = self.DRAWBAR_MAX - x
                canvas.itemconfig(text, fill=self.white if label_number == number else "grey")
        except Exception as e:
            logging.error(e)
