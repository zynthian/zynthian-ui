import tkinter
import logging
from zyngui import zynthian_widget_base
from zyngine.zynthian_engine_setbfree import *
from zyngui import zynthian_gui_config

class zynthian_widget_setbfree(zynthian_widget_base.zynthian_widget_base):
    def __init__(self, parent):
        super().__init__(parent)
        base = self.rows
        self.rows = base // 2
        self.brown = 'dark red'
        self.white = '#fff'
        self.black = '#000'
        self.outline = 'wheat'
        self.drawbars = [['DB 16', self.brown, '16'],
                         ['DB 5 1/3', self.brown, '5⅓'],
                         ['DB 8', self.white, '8'],
                         ['DB 4', self. white, '4'],
                         ['DB 2 2/3', self.black, '2⅔'],
                         ['DB 2', self.white, '2'],
                         ['DB 1 3/5', self.black, '1⅗'],
                         ['DB 1 1/3', self.black, '1⅓'],
                         ['DB 1', self.white, '1']]

        self.widget_canvas = tkinter.Canvas(self,
                                         height=1,
                                         width=1,
                                         bd=0,
                                         highlightthickness=0,
                                         bg='#000' #zynthian_gui_config.color_panel_bg
                                         )
        self.drawbar_nums = {}
        self.drawbar_values = {}
        for i in range(9):
            self.drawbar(i)

    def on_size(self, event):
        super().on_size(event)
        for i in range(9):
            self.size_drawbar(i)

    def refresh_gui(self):
        super().refresh_gui()
        monitors = self.monitors or {}
        canvas = self.widget_canvas
        canvas.pack(anchor=tkinter.CENTER, expand=False)
        for i in range(9):
            self.move_drawbar(i)

    def moveto_group(self, tag, y):
        _, y1, _, _ = self.widget_canvas.bbox(tag)          # current top‑left of the group
        self.widget_canvas.move(tag, 0 # x - x1
                                , y - y1)          # shift by the needed delta
            
    def drawbar(self, i):
        pass

    def size_drawbar(self, i):
        border = 2
        canvas = self.widget_canvas
        canvas.delete(f"bar{i}")
        width = (self.width - 2 * border) // 9
        rect = canvas.create_rectangle(0, 0, 0, 0,
                                       outline=self.outline, fill="#000", tags=f"bar{i}")
        step_height = (self.height // 9)
        tag = f"bar{i}"
        drawbar = self.drawbars[i]
        color = drawbar[1]

        try:
            # position / size drawbar
            canvas.coords(rect, border + 2 + i*width, 0,
                          border + ((i+1) * width) - 2, self.height)
            # handle
            canvas.create_rectangle(border + i*width + 1, 8 * step_height,
                                    border + ((i+1)*width -1), self.height, outline=self.outline, fill=color, tags=tag)
            canvas.create_text((0.5 * width + border + 1 + (i * width), 8.5 * step_height),
                               text=drawbar[2],
                               fill=self.black if drawbar[1] == self.white else self.white,
                               tags=tag)
            nums = []
            for step in range(8):
                # canvas.create_line((border + 1 + (i * width), step * step_height), (border - 1 + ((i + 1) * width), step * step_height), width=1, fill="darkgray", tags=tag)
                num = canvas.create_text((0.5 * width + border + 1 + (i * width), step * step_height + 0.5 * step_height), fill='grey', text=8 - step, tags=tag)
                nums.append(num)
            self.drawbar_nums[i] = nums
            self.drawbar_values[i] = None # Force redraw
                
        except Exception as e:
            logging.error(e);
        
    def move_drawbar(self, i):
        # (full out) 7 - 23 - 39 - 55 - 71 - 87 - 103 - 119 - 127 (full in)
        drawbar = self.drawbars[i]
        value = self.processor.controllers_dict[drawbar[0]].value
        if self.drawbar_values.get(i, None) == value:
            return
        self.drawbar_values[i] = value
        valuex = self.processor.controllers_dict[drawbar[0]].get_value2index()
        border = 2
        canvas = self.widget_canvas
        width = (self.width - 2 * border) // 9
        
        num = 8 - valuex # (value - 7) // 14
        try:
            self.moveto_group(f"bar{i}", # border + i * width, 
                              5 - value * (self.height // 127))
            for x, text in enumerate(self.drawbar_nums[i]):
                if x == num:
                    canvas.itemconfig(text, fill=self.white)
                else:
                    canvas.itemconfig(text, fill="grey")
        except Exception as e:
            logging.error(e);
