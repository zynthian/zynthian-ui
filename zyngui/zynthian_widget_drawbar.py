import tkinter
import logging
from zyngui import zynthian_widget_base
from zyngine.zynthian_engine_setbfree import *
from zyngui import zynthian_gui_config

class zynthian_widget_drawbar(zynthian_widget_base.zynthian_widget_base):
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
        self.drag = {"item": None, "y": 0, 'barnum': None}
        self.widget_canvas.bind("<ButtonPress-1>", self.on_press)
        self.widget_canvas.bind("<B1-Motion>", self.on_motion)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_release)

    def set_processor(self, processor):
        super().set_processor(processor)
        drawbar_ctrls = [k for k, v in self.processor.controllers_dict.items() if hasattr(v, 'drawbar')]
        if (len(drawbar_ctrls) > 0):
            self.drawbars = drawbar_ctrls
            # drawbars = [None] * len(drawbar_ctrls)
            # for i, db in enumerate(drawbar_ctrls):
            #     drawbars[i] = db
            # self.drawbars = drawbars

    def show(self):
        super().show()
        
    def on_press(self, event):
        # the handle under mouse, if any
        for item in reversed(self.widget_canvas.find_overlapping(event.x, event.y, event.x, event.y)):
            tags = self.widget_canvas.gettags(item)
            if "handle" in tags:
                self.drag.update(item=item)
                for tag in tags:
                    if tag.startswith('bar'):
                        try:
                            self.drag.update(barnum=int(tag[3:]))
                        except Exception as e:
                            logging.error(e)
                return

    def on_motion(self, event):
        if self.drag is not None and self.drag["item"]:
            perc = max(0, event.y) / self.height
            barid = self.drawbars[self.drag['barnum']]
            val = (1 - perc) * 127
            self.processor.controllers_dict[barid].set_value(val)

    def on_release(self, event):
        self.drag["item"] = None

    def on_size(self, event):
        super().on_size(event)
        self.widget_canvas.delete("drawbar")
        for i in range(len(self.drawbars)):
            self.draw_drawbar(i)

    def refresh_gui(self):
        super().refresh_gui()
        monitors = self.monitors or {}
        canvas = self.widget_canvas
        canvas.pack(anchor=tkinter.CENTER, expand=False)
        for i in range(len(self.drawbars)):
            self.move_drawbar(i)

    def moveto_group(self, tag, y):
        _, y1, _, _ = self.widget_canvas.bbox(tag)          # current top‑left of the group
        self.widget_canvas.move(tag, 0 # x - x1
                                , y - y1)          # shift by the needed delta
            
    def draw_drawbar(self, i):
        canvas = self.widget_canvas
        tag = f"bar{i}"
        tags = (tag, "drawbar")
        width = (self.width - 2 * self.border) // len(self.drawbars)
        rect = canvas.create_rectangle(0, 0, 0, 0,
                                       outline=self.outline, fill="#000", tags=tags)
        step_height = (self.height // 9)

        drawbar = self.drawbars[i]
        color, text = self.drawbar_settings[i]

        try:
            # position / size drawbar
            canvas.coords(rect, self.border + 2 + i*width, 0,
                          self.border + ((i+1) * width) - 2, self.height)
            # handle
            canvas.create_rectangle(self.border + i*width + 1, 8 * step_height,
                                    self.border + ((i+1)*width -1), self.height,
                                    outline=self.outline, fill=color, tags=(*tags,"handle"))
            canvas.create_text((0.5 * width + self.border + 1 + (i * width), 8.5 * step_height),
                               text=text,
                               fill=self.black if color == self.white else self.white,
                               tags=tags)
            nums = []
            for step in range(8):
                num = canvas.create_text((0.5 * width + self.border + 1 + (i * width), step * step_height + 0.5 * step_height),
                                         fill='grey', text=8 - step, tags=tags)
                nums.append(num)
            self.drawbar_nums[i] = nums
            self.drawbar_values[i] = None # Force redraw
                
        except Exception as e:
            logging.error(e);
        
    def move_drawbar(self, i):
        # (full out) 7 - 23 - 39 - 55 - 71 - 87 - 103 - 119 - 127 (full in)
        drawbar = self.drawbars[i]
        value = self.processor.controllers_dict[drawbar].value
        if self.drawbar_values.get(i, None) == value:
            return
        self.drawbar_values[i] = value
        canvas = self.widget_canvas
        width = (self.width - 2 * self.border) // len(self.drawbars)

        valuex = self.processor.controllers_dict[drawbar].get_value2index()

        if valuex is not None:
            num = 8 - valuex
            try:
                self.moveto_group(f"bar{i}",
                                  5 - value * (self.height // 127))
                for x, text in enumerate(self.drawbar_nums[i]):
                    if x == num:
                        canvas.itemconfig(text, fill=self.white)
                    else:
                        canvas.itemconfig(text, fill="grey")
            except Exception as e:
                logging.error(e);
        else:
            num = 8 - round(value)
            # logging.debug(f'Drawbar {i+1} value {value}')
            try:
                self.moveto_group(f"bar{i}",
                                  ((value + 1) * ((self.height - self.border) / 9)) - (self.height))
                for x, text in enumerate(self.drawbar_nums[i]):
                    if x == num:
                        canvas.itemconfig(text, fill=self.white)
                    else:
                        canvas.itemconfig(text, fill="grey")
            except Exception as e:
                logging.error(e);
            
