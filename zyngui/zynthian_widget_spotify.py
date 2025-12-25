#!/usr/bin/python3
# -*- coding: utf-8 -*-
import tkinter
import logging
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base
from PIL import Image, ImageTk
import requests
from io import BytesIO
from collections import OrderedDict

class zynthian_widget_spotify(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)

        self.widget_canvas = tkinter.Canvas(self,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        self.lbl_title = self.widget_canvas.create_text(
            10, 0,
            anchor="nw",
            font=(
                zynthian_gui_config.font_family,
                int(0.75 * zynthian_gui_config.font_size)
            ),
            fill=zynthian_gui_config.color_tx_off
        )

        self.artwork_image = None
        self.artwork_id = None
        self.image_cache = OrderedDict()  # To store cached images
        self.cache_limit = 20

        self.refresh_count = 0
        self.info_page = 0
        self.refresh_count = 0
        self.info_page = 0

    def show(self):
        self.refresh_count = 0
        self.info_page = 3
        super().show()

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)
        # Update canvas item widths and artwork size
        self.widget_canvas.itemconfigure(self.lbl_title, width=self.width)
        # Resize artwork image if needed
        self.resize_artwork()

    def update_artwork(self):
        """Fetch and display the artwork image from the provided URL with caching."""
        image_url = self.monitors.get("artwork")
        if image_url:
            if image_url in self.image_cache:
                # If the image is cached, retrieve it
                self.artwork_image = self.image_cache[image_url]
            else:
                # Fetch the image
                try:
                    response = requests.get(image_url)
                    img_data = BytesIO(response.content)
                    img = Image.open(img_data)

                    # Resize to square (maintaining aspect ratio)
                    min_dim = min(self.width, min(img.size)) - 20
                    img = img.resize((min_dim, min_dim), Image.ANTIALIAS)

                    # Convert to PhotoImage
                    self.artwork_image = ImageTk.PhotoImage(img)

                    # Cache the image
                    self.image_cache[image_url] = self.artwork_image

                    # Maintain the cache limit
                    if len(self.image_cache) > self.cache_limit:
                        self.image_cache.popitem(last=False)  # Remove the oldest item


                except Exception as e:
                    logging.error("Error loading artwork: %s", e)

            try:
                # Update the canvas image
                if self.artwork_id:
                    self.widget_canvas.itemconfig(self.artwork_id, image=self.artwork_image)
                else:
                    # Create a canvas image item if it doesn't exist
                    self.artwork_id = self.widget_canvas.create_image(self.width // 4, self.height // 4, image=self.artwork_image)

                self.resize_artwork()
            except Exception as e:
                logging.error("Error setting artwork: %s", e)



    def resize_artwork(self):
        """Resize the artwork image if needed during resizing of the widget."""
        if self.artwork_id:
            self.widget_canvas.coords(self.artwork_id, self.width // 2, 20 + (self.height // 2))
            self.widget_canvas.itemconfig(self.artwork_id, image=self.artwork_image)

    def refresh_gui(self):
        self.refresh_count += 1
        if self.monitors["reset"]:
            self.info_page = 0
            self.monitors["reset"] = False
        elif self.refresh_count < 50:
            # Update every 2s
            return
        self.update_artwork()  # Update the artwork on every refresh
        self.refresh_count = 0

        self.widget_canvas.itemconfigure(
            self.lbl_title, text=self.monitors["title"] + '\n' + self.monitors["artist"])
