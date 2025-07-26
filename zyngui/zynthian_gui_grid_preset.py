#!/usr/bin/python3
import tkinter
import math
import os
import copy
import logging
import json

from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_preset import zynthian_gui_preset

class zynthian_gui_grid_preset(zynthian_gui_preset):

    def __init__(self):
        self.grid_cols = 4
        self.grid_rows = 4
        self.grid_size = self.grid_cols * self.grid_rows
        self.grid_buttons = []
        self.grid_frame = None
        self.current_page = 0
        self.total_pages = 0
        self.dir_nav_rows = 2
        self.dir_nav_cols = 5
        self.dir_nav_size = self.dir_nav_rows * self.dir_nav_cols
        self.dir_nav_buttons = []
        self.dir_nav_frame = None
        self.current_dir_page = 0
        self.directory_list = []
        self.current_grid_items = []
        self.scroll_text_data = {}
        self.scroll_timer = None
        self.scroll_speed = 300
        self.current_subdirectory = "SD/User"
        self.all_directories = []
        super().__init__()

    def build_view(self):
        self.processor = self.zyngui.get_current_processor()
        if not self.processor:
            return False
        self.create_full_layout()
        self.load_subdirectory_contents()
        self.fill_directory_navigation()
        self.index = -1
        self.fill_list()
        self.set_select_path()
        self.main_frame.update_idletasks()
        if self.current_subdirectory != "Favourite" and self.all_directories:
            if len(self.all_directories) > 0:
                self.dir_nav_click(1)
        elif self.current_subdirectory == "Favourite":
            self.fill_list()
        return True

    def create_full_layout(self):
        if not hasattr(self, 'full_container'):
            self.full_container = tkinter.Frame(
                self.main_frame,
                bg=zynthian_gui_config.color_panel_bg,
                bd=0,
                relief='flat'
            )
            self.full_container.grid(
                row=0, column=0,
                columnspan=10,
                rowspan=10,
                padx=0, pady=0,
                sticky="nsew"
            )
            for i in range(10):
                self.main_frame.columnconfigure(i, weight=1)
                self.main_frame.rowconfigure(i, weight=1)
        self.create_directory_navigation()
        self.create_main_grid()

    def create_directory_navigation(self):
        if not self.dir_nav_frame:
            self.dir_nav_frame = tkinter.Frame(
                self.full_container,
                bg=zynthian_gui_config.color_panel_bg,
                bd=0,
                relief='flat'
            )
            self.dir_nav_frame.grid(
                row=1, column=0,
                columnspan=1,
                padx=5, pady=(5, 5),
                sticky="ew",
                ipady=2
            )

        for button in self.dir_nav_buttons:
            button.destroy()
        self.dir_nav_buttons = []
        
        if hasattr(self, 'dir_page_prev_button'):
            self.dir_page_prev_button.destroy()
        if hasattr(self, 'dir_page_next_button'):
            self.dir_page_next_button.destroy()
        if hasattr(self, 'dir_page_label'):
            self.dir_page_label.destroy()

        for row in range(self.dir_nav_rows):
            for col in range(self.dir_nav_cols):
                btn_index = row * self.dir_nav_cols + col
                
                if row == 0 and col == 0:
                    self.subdir_var = tkinter.StringVar()
                    self.subdir_var.set("SD/User")
                    
                    self.subdir_dropdown = tkinter.OptionMenu(
                        self.dir_nav_frame,
                        self.subdir_var,
                        "SD/User",
                        "SD/System", 
                        "USB",
                        "Favourite",
                        command=self.on_subdirectory_change
                    )
                    
                    self.subdir_dropdown.config(
                        font=zynthian_gui_config.font_listbox,
                        bg=zynthian_gui_config.color_panel_hl,
                        fg=zynthian_gui_config.color_panel_tx,
                        relief='flat',
                        bd=0,
                        width=8,
                        height=1
                    )
                    
                    self.subdir_dropdown['menu'].config(
                        font=zynthian_gui_config.font_listbox,
                        bg=zynthian_gui_config.color_panel_bg,
                        fg=zynthian_gui_config.color_panel_tx,
                        relief='flat',
                        bd=0
                    )
                    
                    self.subdir_dropdown.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                    
                    button = tkinter.Button(
                        self.dir_nav_frame,
                        text="",
                        width=12,
                        height=1,
                        font=zynthian_gui_config.font_listbox,
                        bg=zynthian_gui_config.color_panel_bg,
                        fg=zynthian_gui_config.color_panel_tx,
                        relief='flat',
                        bd=0,
                        command=lambda: None,
                        state='disabled'
                    )
                    button.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                    button.grid_remove()
                    
                elif row == 1 and col == 0:
                    page_nav_frame = tkinter.Frame(
                        self.dir_nav_frame,
                        bg=zynthian_gui_config.color_panel_bg,
                        bd=0,
                        relief='flat'
                    )
                    page_nav_frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                    
                    page_nav_frame.columnconfigure(0, weight=1)
                    page_nav_frame.columnconfigure(1, weight=1)
                    page_nav_frame.rowconfigure(0, weight=1)
                    
                    self.dir_page_prev_button = tkinter.Button(
                        page_nav_frame,
                        text="◀",
                        width=4,
                        height=1,
                        font=zynthian_gui_config.font_listbox,
                        bg=zynthian_gui_config.color_panel_hl,
                        fg=zynthian_gui_config.color_panel_tx,
                        relief='flat',
                        bd=0,
                        command=lambda: self.handle_dir_page_button_click('prev'),
                        justify='center'
                    )
                    self.dir_page_prev_button.grid(row=0, column=0, padx=(0, 1), pady=0, sticky="nsew")
                    
                    self.dir_page_next_button = tkinter.Button(
                        page_nav_frame,
                        text="▶",
                        width=4,
                        height=1,
                        font=zynthian_gui_config.font_listbox,
                        bg=zynthian_gui_config.color_panel_hl,
                        fg=zynthian_gui_config.color_panel_tx,
                        relief='flat',
                        bd=0,
                        command=lambda: self.handle_dir_page_button_click('next'),
                        justify='center'
                    )
                    self.dir_page_next_button.grid(row=0, column=1, padx=(1, 0), pady=0, sticky="nsew")
                    
                    button = tkinter.Button(
                        self.dir_nav_frame,
                        text="",
                        width=12,
                        height=1,
                        font=zynthian_gui_config.font_listbox,
                        bg=zynthian_gui_config.color_panel_bg,
                        fg=zynthian_gui_config.color_panel_tx,
                        relief='flat',
                        bd=0,
                        command=lambda: None,
                        state='disabled'
                    )
                    button.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                    button.grid_remove()
                    
                else:
                    button = tkinter.Button(
                        self.dir_nav_frame,
                        text="",
                        width=12,
                        height=1,
                        font=zynthian_gui_config.font_listbox,
                        bg=zynthian_gui_config.color_panel_hl,
                        fg=zynthian_gui_config.color_panel_tx,
                        relief='flat',
                        bd=0,
                        command=lambda i=btn_index: self.dir_nav_click(i),
                        justify='center'
                    )
                    button.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                
                self.dir_nav_buttons.append(button)

        for row in range(self.dir_nav_rows):
            self.dir_nav_frame.rowconfigure(row, weight=1)
        for col in range(self.dir_nav_cols):
            self.dir_nav_frame.columnconfigure(col, weight=1)

    def create_main_grid(self):
        if not self.grid_frame:
            self.grid_frame = tkinter.Frame(
                self.full_container,
                bg=zynthian_gui_config.color_panel_bg,
                bd=0,
                relief='flat'
            )
            self.grid_frame.grid(
                row=2, column=0,
                columnspan=1,
                padx=5, pady=5,
                sticky="nsew"
            )
            
            self.full_container.rowconfigure(2, weight=1)
            self.full_container.columnconfigure(0, weight=1)

        for button in self.grid_buttons:
            button.destroy()
        self.grid_buttons = []
        self.scroll_text_data = {}
        
        if hasattr(self, 'soundfont_info_label'):
            self.soundfont_info_label.destroy()
        if hasattr(self, 'preset_info_label'):
            self.preset_info_label.destroy()
        if hasattr(self, 'page_info_label'):
            self.page_info_label.destroy()
        if hasattr(self, 'favourite_canvas'):
            self.favourite_canvas.destroy()

        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                btn_index = row * self.grid_cols + col
                button = tkinter.Button(
                    self.grid_frame,
                    text="",
                    width=22,
                    height=1,
                    font=zynthian_gui_config.font_listbox,
                    bg=zynthian_gui_config.color_panel_bg,
                    fg=zynthian_gui_config.color_panel_tx,
                    relief='flat',
                    bd=0,
                    command=lambda i=btn_index: self.grid_button_click(i),
                    wraplength=180,
                    justify='center'
                )
                button.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                self.grid_buttons.append(button)

        for row in range(self.grid_rows):
            self.grid_frame.rowconfigure(row, weight=1)
        for col in range(self.grid_cols):
            self.grid_frame.columnconfigure(col, weight=1)

        
        info_row = self.grid_rows
        info_frame = tkinter.Frame(
            self.full_container,
            bg=zynthian_gui_config.color_panel_bg,
            bd=0,
            relief='flat'
        )
        info_frame.grid(row=info_row, column=0, columnspan=1, padx=5, pady=5, sticky="nsew")
        info_frame.rowconfigure(0, weight=1)
        info_frame.rowconfigure(1, weight=1)
        info_frame.columnconfigure(0, weight=0)
        info_frame.columnconfigure(1, weight=0)
        info_frame.columnconfigure(2, weight=3)
        info_frame.columnconfigure(3, weight=3)
        info_frame.columnconfigure(4, weight=1)

        
        self.soundfont_page_prev_button = tkinter.Button(
            info_frame,
            text="◀",
            width=4,
            height=1,
            font=zynthian_gui_config.font_listbox,
            bg=zynthian_gui_config.color_panel_hl,
            fg=zynthian_gui_config.color_panel_tx,
            relief='flat',
            bd=0,
            command=self.prev_soundfont_page,
            justify='center'
        )
        self.soundfont_page_prev_button.grid(row=0, column=0, rowspan=2, padx=(0,0), pady=0, sticky="nsew")

       
        self.soundfont_page_next_button = tkinter.Button(
            info_frame,
            text="▶",
            width=4,
            height=1,
            font=zynthian_gui_config.font_listbox,
            bg=zynthian_gui_config.color_panel_hl,
            fg=zynthian_gui_config.color_panel_tx,
            relief='flat',
            bd=0,
            command=self.next_soundfont_page,
            justify='center'
        )
        self.soundfont_page_next_button.grid(row=0, column=1, rowspan=2, padx=(0,4), pady=0, sticky="nsew")

       
        font_family = zynthian_gui_config.font_listbox[0]
        font_size = zynthian_gui_config.font_listbox[1]
        preset_font = (font_family, int(1.5 * font_size), "bold")
        self.preset_info_label = tkinter.Label(
            info_frame,
            text="",
            font=preset_font,
            bg=zynthian_gui_config.color_panel_bg,
            fg=zynthian_gui_config.color_panel_tx,
            relief='flat',
            bd=0,
            justify='center',
            anchor='center'
        )
        self.preset_info_label.grid(row=0, column=2, columnspan=2, padx=0, pady=0, sticky="ew")

        self.soundfont_info_label = tkinter.Label(
            info_frame,
            text="",
            font=zynthian_gui_config.font_listbox,
            bg=zynthian_gui_config.color_panel_bg,
            fg=zynthian_gui_config.color_panel_tx,
            relief='flat',
            bd=0,
            justify='center',
            anchor='center'
        )
        self.soundfont_info_label.grid(row=1, column=2, columnspan=2, padx=0, pady=0, sticky="ew")

        self.favourite_canvas = tkinter.Canvas(
            info_frame,
            width=80,
            height=40,
            bg=zynthian_gui_config.color_panel_bg,
            highlightthickness=0,
            relief='flat',
            bd=0
        )
        self.favourite_canvas.grid(row=0, column=4, rowspan=2, padx=2, pady=2, sticky="nsew")
        self.favourite_canvas.bind("<Button-1>", lambda e: self.toggle_favourite())
        self.favourite_canvas.after(10, self.draw_star_button)

    def format_directory_button_text(self, text, max_width=13):
        """Format text to fit directory button with automatic scaling"""
        if not text:
            return ""
        
        clean_text = text.replace('\n', ' ').strip()
        
        if len(clean_text) <= max_width:
            return clean_text
        
        words = clean_text.split()
        if len(words) > 1:
            if len(words[0]) + 1 + 1 <= max_width:
                return f"{words[0]}.{words[1][0] if words[1] else ''}"
            elif len(words[0][:2]) + 1 + len(words[1]) <= max_width:
                return f"{words[0][:2]}.{words[1]}"
        
        return clean_text[:max_width-3] + "..." if len(clean_text) > max_width else clean_text

    def fill_directory_navigation(self):
        if not hasattr(self, 'all_directories'):
            self.all_directories = []
            
        if not hasattr(self, 'current_dir_page'):
            self.current_dir_page = 0
            
        available_cells = self.dir_nav_size - 2
        self.total_dir_pages = math.ceil(len(self.all_directories) / available_cells) if self.all_directories else 1
        
        start_idx = self.current_dir_page * available_cells
        end_idx = min(start_idx + available_cells, len(self.all_directories))
        page_dirs = self.all_directories[start_idx:end_idx]
        
        if hasattr(self, 'dir_page_label'):
            if self.total_dir_pages > 1:
                self.dir_page_label.config(
                    text=f"{self.current_dir_page + 1}/{self.total_dir_pages}",
                    bg=zynthian_gui_config.color_panel_hl,
                    fg=zynthian_gui_config.color_panel_tx
                )
            else:
                self.dir_page_label.config(
                    text="",
                    bg=zynthian_gui_config.color_panel_bg,
                    fg=zynthian_gui_config.color_panel_tx
                )
        
        for i, button in enumerate(self.dir_nav_buttons):
            if i == 0 or i == 5:
                continue
                
            dir_index = i - 2 if i > 5 else i - 1
            
            if dir_index < len(page_dirs):
                dir_info = page_dirs[dir_index]
                formatted_text = self.format_directory_button_text(dir_info['display_name'])
                button.config(
                    text=formatted_text,
                    state='normal',
                    bg=zynthian_gui_config.color_panel_hl,
                    fg=zynthian_gui_config.color_panel_tx
                )
                button.dir_info = dir_info
            else:
                button.config(
                    text="",
                    state='disabled',
                    bg=zynthian_gui_config.color_panel_bg,
                    fg=zynthian_gui_config.color_tx_off
                )
                button.dir_info = None
        
        if hasattr(self, 'dir_page_prev_button') and hasattr(self, 'dir_page_next_button'):
            if self.current_dir_page > 0:
                self.dir_page_prev_button.config(
                    state='normal',
                    bg=zynthian_gui_config.color_panel_hl,
                    fg=zynthian_gui_config.color_panel_tx
                )
            else:
                self.dir_page_prev_button.config(
                    state='disabled',
                    bg=zynthian_gui_config.color_panel_bg,
                    fg=zynthian_gui_config.color_tx_off
                )
            
            if self.current_dir_page < self.total_dir_pages - 1:
                self.dir_page_next_button.config(
                    state='normal',
                    bg=zynthian_gui_config.color_panel_hl,
                    fg=zynthian_gui_config.color_panel_tx
                )
            else:
                self.dir_page_next_button.config(
                    state='disabled',
                    bg=zynthian_gui_config.color_panel_bg,
                    fg=zynthian_gui_config.color_tx_off
                )
        
        if hasattr(self, 'dir_selection_index') and self.dir_selection_index is not None:
            if self.dir_selection_index >= len(page_dirs):
                self.dir_selection_index = max(0, len(page_dirs) - 1) if page_dirs else 0
            if page_dirs:
                self.highlight_dir_selection()
        
        self.set_select_path()

    def get_soundfont_list_from_directory(self, directory_path):
        soundfont_list = []
        if not os.path.isdir(directory_path):
            return soundfont_list
        try:
            for f in sorted(os.listdir(directory_path)):
                if f.startswith('.'):
                    continue
                fpath = os.path.join(directory_path, f)
                if os.path.isfile(fpath):
                    filename, filext = os.path.splitext(f)
                    if filext.lower() in ['.sf2', '.sf3']:
                        title = filename.replace('_', ' ')
                        soundfont_list.append([fpath, 0, title, 'soundfont', f])
            if not soundfont_list:
                for item in sorted(os.listdir(directory_path)):
                    if item.startswith('.'):
                        continue
                    item_path = os.path.join(directory_path, item)
                    if os.path.isdir(item_path):
                        sub_soundfonts = self.get_soundfont_list_from_subdirectory(item_path, item)
                        soundfont_list.extend(sub_soundfonts)
            return soundfont_list
        except Exception:
            return soundfont_list

    def get_soundfont_list_from_subdirectory(self, subdir_path, subdir_name):
        soundfont_list = []
        try:
            for f in sorted(os.listdir(subdir_path)):
                if f.startswith('.'):
                    continue
                fpath = os.path.join(subdir_path, f)
                if os.path.isfile(fpath):
                    filename, filext = os.path.splitext(f)
                    if filext.lower() in ['.sf2', '.sf3']:
                        title = f"{subdir_name}/{filename}".replace('_', ' ')
                        soundfont_list.append([fpath, 0, title, 'soundfont', f])
        except Exception:
            pass
        return soundfont_list

    def dir_nav_click(self, btn_index):
        button = self.dir_nav_buttons[btn_index]
        if hasattr(button, 'dir_info') and button.dir_info:
            dir_info = button.dir_info
            self.dir_selection_index = btn_index
            self.highlight_dir_selection()
            if dir_info['type'] == 'directory':
                directory_path = dir_info['path']
                try:
                    current_preset = None
                    current_bank = None
                    current_preset_index = None
                    current_soundfont_path = None
                    if hasattr(self.processor, 'preset_info') and self.processor.preset_info:
                        current_preset = copy.deepcopy(self.processor.preset_info)
                        current_soundfont_path = current_preset[0] if current_preset[0] else None
                    if hasattr(self.processor, 'bank_info') and self.processor.bank_info:
                        current_bank = copy.deepcopy(self.processor.bank_info)
                        if not current_soundfont_path and current_bank[0]:
                            current_soundfont_path = current_bank[0]
                    if hasattr(self.processor, 'preset_index'):
                        current_preset_index = self.processor.preset_index
                    soundfont_list = self.get_soundfont_list_from_directory(directory_path)
                    self.list_data = soundfont_list
                    if current_bank:
                        self.processor.bank_info = current_bank
                    if current_preset_index is not None:
                        self.processor.preset_index = current_preset_index
                    self.current_directory_info = {
                        'name': dir_info['name'],
                        'path': directory_path
                    }
                    if hasattr(self, 'grid_selection_index'):
                        delattr(self, 'grid_selection_index')
                    self.index = -1
                    if hasattr(self, 'zselector') and self.zselector:
                        self.zselector.zctrl.set_value(0, False)
                    self.show_current_presets_in_grid()
                    self.set_select_path()
                    self.main_frame.update_idletasks()
                    self.main_frame.after(100, self.update_favourite_button_state)
                except Exception:
                    pass

    def show_current_presets_in_grid(self):
        if not self.processor:
            return
        grid_items = []
        if hasattr(self, 'list_data') and self.list_data:
            for item in self.list_data:
                if item[0] is not None:
                    display_text = item[2] if item[2] else "Unknown"
                    if display_text.startswith("❤"):
                        display_text = display_text[1:]
                    grid_items.append({
                        'name': display_text,
                        'preset_info': item,
                        'display_text': display_text,
                        'type': 'soundfont'
                    })
        if not grid_items:
            grid_items.append({
                'name': "No soundfonts found",
                'preset_info': None,
                'display_text': "No soundfonts found in this directory",
                'type': 'message'
            })
        self.display_items_in_grid(grid_items)
        self.main_frame.after(50, self.update_info_display)
        self.main_frame.after(100, self.update_favourite_button_state)

    def display_items_in_grid(self, items):
        self.current_grid_items = items
        self.current_page = 0
        available_grid_cells = 16
        self.total_pages = math.ceil(len(items) / available_grid_cells) if items else 1
        self.fill_grid_with_items()
        self.update_page_indicator()

    def fill_grid_with_items(self):
        self.stop_text_scrolling()
        if not hasattr(self, 'current_grid_items'):
            self.current_grid_items = []
        available_grid_cells = 16
        start_idx = self.current_page * available_grid_cells
        end_idx = min(start_idx + available_grid_cells, len(self.current_grid_items))
        page_items = self.current_grid_items[start_idx:end_idx]
        for i, button in enumerate(self.grid_buttons):
            if i < len(page_items):
                item = page_items[i]
                display_text = self.format_button_text(item['display_text'])
                
                if item['type'] == 'message':
                    button.config(
                        text=display_text,
                        state='disabled',
                        bg=zynthian_gui_config.color_panel_hl,
                        fg=zynthian_gui_config.color_tx_off
                    )
                    button.grid_item = item
                else:
                    bg_color = zynthian_gui_config.color_panel_bg
                    prefix = "🎵 "
                    button.config(
                        text=prefix + display_text,
                        state='normal',
                        bg=bg_color,
                        fg=zynthian_gui_config.color_panel_tx
                    )
                    button.grid_item = item
                    if len(item['display_text']) > 30:
                        self.start_text_scrolling(i, prefix + item['display_text'])
            else:
                button.config(
                    text="",
                    state='disabled',
                    bg=zynthian_gui_config.color_panel_hl,
                    fg=zynthian_gui_config.color_tx_off
                )
                button.grid_item = None
        self.update_info_display()
        self.update_favourite_button_state()
        if hasattr(self, 'grid_selection_index') and self.grid_selection_index is not None:
            if self.grid_selection_index >= len(page_items):
                self.grid_selection_index = max(0, len(page_items) - 1) if page_items else 0
            if page_items:
                self.highlight_grid_selection()

    def grid_button_click(self, btn_index):
        button = self.grid_buttons[btn_index]
        if hasattr(button, 'grid_item') and button.grid_item:
            item = button.grid_item
            self.grid_selection_index = btn_index
            self.highlight_grid_selection()
            if item['type'] == 'message':
                return
            elif item['type'] == 'soundfont':
                preset_info = item['preset_info']
                if hasattr(self, 'current_directory_info') and self.current_directory_info:
                    try:
                        soundfont_preset = [
                            preset_info[0],
                            0,
                            preset_info[2],
                            'soundfont',
                            preset_info[4]
                        ]
                        result = self.processor.engine.set_preset(self.processor, soundfont_preset)
                        if result == "SOUNDFONT_LOADED":
                            delattr(self, 'current_directory_info')
                            self.fill_list()
                            if hasattr(self.processor, 'refresh_controllers'):
                                self.processor.refresh_controllers()
                            self.show_current_presets_in_grid()
                            if self.list_data:
                                self.select(0)
                            self.main_frame.after(50, self.update_info_display)
                            self.main_frame.after(100, self.update_favourite_button_state)
                        elif result:
                            delattr(self, 'current_directory_info')
                            self.fill_list()
                            self.show_current_presets_in_grid()
                            self.main_frame.after(50, self.update_info_display)
                            self.main_frame.after(100, self.update_favourite_button_state)
                    except Exception:
                        pass
                else:
                    preset_index = None
                    for i, list_item in enumerate(self.list_data):
                        if (list_item[0] == preset_info[0] and 
                            list_item[2] == preset_info[2]):
                            preset_index = i
                            break
                    if preset_index is not None:
                        self.index = preset_index
                        if self.zselector:
                            val = self.get_counter_from_index(self.index)
                            self.zselector.zctrl.set_value(val, False)
                        result = self.processor.set_preset(preset_index)
                        if result == "SOUNDFONT_LOADED":
                            self.fill_list()
                            if hasattr(self.processor, 'refresh_controllers'):
                                self.processor.refresh_controllers()
                            self.show_current_presets_in_grid()
                        self.main_frame.after(50, self.update_info_display)
                        self.main_frame.after(100, self.update_favourite_button_state)
                    else:
                        try:
                            result = self.processor.set_preset(0)
                            if result == "SOUNDFONT_LOADED":
                                self.fill_list()
                                if hasattr(self.processor, 'refresh_controllers'):
                                    self.processor.refresh_controllers()
                                self.show_current_presets_in_grid()
                            elif result:
                                self.select_action(0, 'S')
                            self.main_frame.after(50, self.update_info_display)
                            self.main_frame.after(100, self.update_favourite_button_state)
                        except Exception:
                            pass

    def format_button_text(self, text, max_length=35):
        if len(text) <= max_length:
            return text
        
        words = text.split()
        if len(words) > 1:
            if len(words[0]) <= max_length:
                result = words[0]
                for word in words[1:]:
                    if len(result + " " + word) <= max_length:
                        result += " " + word
                    else:
                        break
                if len(result) < len(text):
                    result += "..."
                return result
        
        return text[:max_length-3] + "..." if len(text) > max_length else text

    def start_text_scrolling(self, button_index, full_text):
        if len(full_text) <= 35:
            return
            
        self.scroll_text_data[button_index] = {
            'full_text': full_text,
            'scroll_pos': 0,
            'max_length': 35
        }
        
        if self.scroll_timer is None:
            self.scroll_timer = self.main_frame.after(self.scroll_speed, self.update_scrolling_text)

    def update_scrolling_text(self):
        any_scrolling = False
        
        for btn_index, scroll_data in self.scroll_text_data.items():
            if btn_index < len(self.grid_buttons):
                button = self.grid_buttons[btn_index]
                if button['state'] == 'normal':
                    full_text = scroll_data['full_text']
                    scroll_pos = scroll_data['scroll_pos']
                    max_length = scroll_data['max_length']
                    
                    if len(full_text) > max_length:
                        if scroll_pos + max_length <= len(full_text):
                            visible_text = full_text[scroll_pos:scroll_pos + max_length]
                        else:
                            remaining = max_length - (len(full_text) - scroll_pos)
                            visible_text = full_text[scroll_pos:] + " | " + full_text[:remaining-3]
                        
                        button.config(text=visible_text)
                        scroll_data['scroll_pos'] = (scroll_pos + 1) % (len(full_text) + 3)
                        any_scrolling = True
        
        if any_scrolling:
            self.scroll_timer = self.main_frame.after(self.scroll_speed, self.update_scrolling_text)
        else:
            self.scroll_timer = None

    def stop_text_scrolling(self):
        if self.scroll_timer:
            self.main_frame.after_cancel(self.scroll_timer)
            self.scroll_timer = None
        self.scroll_text_data = {}

    def fill_list(self):
        if not self.processor:
            return
        if self.current_subdirectory == "Favourite":
            self.processor.set_show_fav_presets(True)
            self.processor.load_preset_list()
            self.list_data = self.processor.preset_list.copy() if self.processor.preset_list else []
            self.index = -1
            self.show_current_presets_in_grid()
            self.main_frame.after(50, self.update_info_display)
            return
        self.processor.set_show_fav_presets(False)
        if hasattr(self, 'current_directory_info') and self.current_directory_info:
            self.index = -1
            self.fill_directory_navigation()
            self.show_current_presets_in_grid()
            self.main_frame.after(50, self.update_info_display)
            return
        self.load_subdirectory_contents()
        self.fill_directory_navigation()
        if hasattr(self.processor, 'get_bank_list'):
            self.processor.bank_list = self.processor.get_bank_list()
        self.processor.load_preset_list()
        original_preset_list = self.processor.preset_list.copy() if self.processor.preset_list else []
        self.list_data = [item for item in original_preset_list if item[0] is not None and (not item[2] or not item[2].startswith('>')) and not (item[0] is not None and os.path.isdir(item[0]))]
        self.index = -1
        if self.all_directories and len(self.all_directories) > 0:
            self.show_current_presets_in_grid()
        else:
            self.show_current_presets_in_grid()
        self.main_frame.after(50, self.update_info_display)

    def select(self, index=None, set_zctrl=True):
        if index is None:
            index = self.index
        
        if 0 <= index < len(self.list_data):
            index = self.skip_separators(index)
            if index is None:
                return
        
        self.index = index
        
        valid_items = [item for item in self.list_data if item[0] is not None]
        if index >= 0 and index < len(self.list_data) and self.list_data[index][0] is not None:
            try:
                valid_index = valid_items.index(self.list_data[index])
                new_page = valid_index // self.grid_size
                
                if new_page != self.current_page:
                    self.current_page = new_page
                    self.fill_grid_with_items()
                else:
                    self.update_selection_highlight()
            except ValueError:
                pass

        if set_zctrl and self.shown and self.zselector and index >= 0:
            val = self.get_counter_from_index(self.index)
            if val != self.zselector.zctrl.value:
                self.zselector.zctrl.set_value(val, False)

    def skip_separators(self, index):
        if 0 <= index < len(self.list_data) and self.list_data[index][0] is None:
            if self.index <= index:
                for i in range(index, len(self.list_data)):
                    if self.list_data[i][0] is not None:
                        return i
                for i in range(index, -1, -1):
                    if self.list_data[i][0] is not None:
                        return i
            else:
                for i in range(index, -1, -1):
                    if self.list_data[i][0] is not None:
                        return i
                for i in range(index, len(self.list_data)):
                    if self.list_data[i][0] is not None:
                        return i
            return None
        return index

    def update_selection_highlight(self):
        if self.index < 0 or self.index >= len(self.list_data):
            for i, button in enumerate(self.grid_buttons):
                if button['state'] == 'normal':
                    button.config(
                        bg=zynthian_gui_config.color_panel_bg,
                        fg=zynthian_gui_config.color_panel_tx
                    )
            return
            
        for i, button in enumerate(self.grid_buttons):
            if hasattr(button, 'original_index') and button.original_index == self.index:
                button.config(
                    bg=zynthian_gui_config.color_ctrl_bg_on,
                    fg=zynthian_gui_config.color_ctrl_tx
                )
            elif button['state'] == 'normal':
                button.config(
                    bg=zynthian_gui_config.color_panel_bg,
                    fg=zynthian_gui_config.color_panel_tx
                )

    def arrow_up(self):
        valid_items = [item for item in self.list_data if item[0] is not None]
        if self.index < len(self.list_data) and self.list_data[self.index][0] is not None:
            try:
                valid_index = valid_items.index(self.list_data[self.index])
                new_valid_index = valid_index - self.grid_cols
                if new_valid_index >= 0:
                    new_index = self.list_data.index(valid_items[new_valid_index])
                    self.select(new_index)
                elif hasattr(self, 'total_pages') and self.total_pages > 1 and self.current_page > 0:
                    self.prev_soundfont_page()
                    start_idx = self.current_page * self.grid_size
                    page_items = len(self.current_grid_items[start_idx:start_idx + self.grid_size])
                    last_row_start = ((page_items - 1) // self.grid_cols) * self.grid_cols
                    col = valid_index % self.grid_cols
                    new_page_index = min(last_row_start + col, page_items - 1)
                    new_valid_index = start_idx + new_page_index
                    if new_valid_index < len(valid_items):
                        new_index = self.list_data.index(valid_items[new_valid_index])
                        self.select(new_index, False)
            except (ValueError, IndexError):
                pass

    def arrow_down(self):
        valid_items = [item for item in self.list_data if item[0] is not None]
        if self.index < len(self.list_data) and self.list_data[self.index][0] is not None:
            try:
                valid_index = valid_items.index(self.list_data[self.index])
                new_valid_index = valid_index + self.grid_cols
                if new_valid_index < len(valid_items):
                    new_index = self.list_data.index(valid_items[new_valid_index])
                    self.select(new_index)
                elif hasattr(self, 'total_pages') and self.total_pages > 1 and self.current_page < self.total_pages - 1:
                    self.next_soundfont_page()
                    start_idx = self.current_page * self.grid_size
                    col = valid_index % self.grid_cols
                    new_page_index = col
                    new_valid_index = start_idx + new_page_index
                    if new_valid_index < len(valid_items):
                        new_index = self.list_data.index(valid_items[new_valid_index])
                        self.select(new_index, False)
            except (ValueError, IndexError):
                pass

    def arrow_left(self):
        valid_items = [item for item in self.list_data if item[0] is not None]
        if self.index < len(self.list_data) and self.list_data[self.index][0] is not None:
            try:
                valid_index = valid_items.index(self.list_data[self.index])
                if valid_index % self.grid_cols > 0:
                    new_valid_index = valid_index - 1
                    new_index = self.list_data.index(valid_items[new_valid_index])
                    self.select(new_index)
            except (ValueError, IndexError):
                pass

    def arrow_right(self):
        valid_items = [item for item in self.list_data if item[0] is not None]
        if self.index < len(self.list_data) and self.list_data[self.index][0] is not None:
            try:
                valid_index = valid_items.index(self.list_data[self.index])
                if (valid_index % self.grid_cols < self.grid_cols - 1 and 
                    valid_index + 1 < len(valid_items)):
                    new_valid_index = valid_index + 1
                    new_index = self.list_data.index(valid_items[new_valid_index])
                    self.select(new_index)
            except (ValueError, IndexError):
                pass

    def return_to_processor_bank(self):
        if hasattr(self, 'current_directory_info'):
            delattr(self, 'current_directory_info')
            self.load_subdirectory_contents()
            self.fill_directory_navigation()
            self.fill_list()
            self.set_select_path()
            if self.all_directories and len(self.all_directories) > 0:
                self.dir_selection_index = 1
                self.highlight_dir_selection()
                self.main_frame.after(100, lambda: self.dir_nav_click(1))
            else:
                self.show_current_presets_in_grid()

    def back_navigation(self):
        if hasattr(self, 'current_directory_info') and self.current_directory_info:
            self.return_to_processor_bank()
            return True
        return False

    def zynpot_cb(self, i, dval):
        if i == 0:
            if hasattr(self, 'all_directories'):
                available_cells = self.dir_nav_size - 2
                if len(self.all_directories) > available_cells:
                    if dval > 0:
                        self.next_dir_page()
                    elif dval < 0:
                        self.prev_dir_page()
                    return True
        elif i == 1:
            if hasattr(self, 'all_directories') and self.all_directories:
                if dval > 0:
                    self.next_dir_cell()
                elif dval < 0:
                    self.prev_dir_cell()
                return True
        elif i == 2:
            if hasattr(self, 'current_grid_items') and hasattr(self, 'total_pages') and self.total_pages > 1:
                if dval > 0:
                    self.next_soundfont_page()
                elif dval < 0:
                    self.prev_soundfont_page()
                return True
        elif i == 3:
            if hasattr(self, 'current_grid_items') and self.current_grid_items:
                if dval > 0:
                    self.next_grid_cell()
                elif dval < 0:
                    self.prev_grid_cell()
                return True
        elif super().zynpot_cb(i, dval):
            return True
        return False
    
    def next_dir_page(self):
        if hasattr(self, 'all_directories'):
            available_cells = self.dir_nav_size - 2
            max_pages = math.ceil(len(self.all_directories) / available_cells)
            if self.current_dir_page < max_pages - 1:
                self.current_dir_page += 1
                self.dir_selection_index = 1
                self.fill_directory_navigation()
                self.highlight_dir_selection()
                self.set_select_path()
    
    def prev_dir_page(self):
        if self.current_dir_page > 0:
            self.current_dir_page -= 1
            self.dir_selection_index = 1
            self.fill_directory_navigation()
            self.highlight_dir_selection()
            self.set_select_path()

    def next_dir_cell(self):
        if not hasattr(self, 'all_directories') or not self.all_directories:
            return
            
        if not hasattr(self, 'dir_selection_index'):
            self.dir_selection_index = 1
        else:
            available_cells = self.dir_nav_size - 2
            start_idx = self.current_dir_page * available_cells
            end_idx = min(start_idx + available_cells, len(self.all_directories))
            page_dirs_count = end_idx - start_idx
            
            self.dir_selection_index += 1
            
            if self.dir_selection_index == 0:
                self.dir_selection_index = 1
            elif self.dir_selection_index == 5:
                self.dir_selection_index = 6
            
            if self.dir_selection_index >= page_dirs_count + 2:
                max_pages = math.ceil(len(self.all_directories) / available_cells)
                if self.current_dir_page < max_pages - 1:
                    self.next_dir_page()
                    self.dir_selection_index = 1
                else:
                    self.dir_selection_index = page_dirs_count + 1
        
        self.highlight_dir_selection()

    def prev_dir_cell(self):
        if not hasattr(self, 'all_directories') or not self.all_directories:
            return
            
        if not hasattr(self, 'dir_selection_index'):
            self.dir_selection_index = 1
        else:
            self.dir_selection_index -= 1
            
            if self.dir_selection_index == 0:
                self.dir_selection_index = -1
            elif self.dir_selection_index == 5:
                self.dir_selection_index = 4
            
            if self.dir_selection_index < 1:
                if self.current_dir_page > 0:
                    self.prev_dir_page()
                    available_cells = self.dir_nav_size - 2
                    start_idx = self.current_dir_page * available_cells
                    end_idx = min(start_idx + available_cells, len(self.all_directories))
                    page_dirs_count = end_idx - start_idx
                    self.dir_selection_index = page_dirs_count + 1
                else:
                    self.dir_selection_index = 1
        
        self.highlight_dir_selection()

    def highlight_dir_selection(self):
        if not hasattr(self, 'dir_selection_index'):
            return
            
        for i, button in enumerate(self.dir_nav_buttons):
            if button['state'] == 'normal':
                button.config(
                    bg=zynthian_gui_config.color_panel_hl,
                    fg=zynthian_gui_config.color_panel_tx
                )
        
        if (hasattr(self, 'dir_selection_index') and 
            0 <= self.dir_selection_index < len(self.dir_nav_buttons) and
            self.dir_selection_index != 0 and self.dir_selection_index != 5 and
            self.dir_nav_buttons[self.dir_selection_index]['state'] == 'normal'):
            
            self.dir_nav_buttons[self.dir_selection_index].config(
                bg=zynthian_gui_config.color_ctrl_bg_on,
                fg=zynthian_gui_config.color_ctrl_tx
            )

    def select_current_dir_cell(self):
        if (hasattr(self, 'dir_selection_index') and 
            0 <= self.dir_selection_index < len(self.dir_nav_buttons) and
            self.dir_selection_index != 0 and self.dir_selection_index != 5):
            
            button = self.dir_nav_buttons[self.dir_selection_index]
            if button['state'] == 'normal':
                self.dir_nav_click(self.dir_selection_index)
                return True
        return False

    def next_soundfont_page(self):
        if hasattr(self, 'current_grid_items') and hasattr(self, 'total_pages'):
            if self.current_page < self.total_pages - 1:
                self.current_page += 1
                if hasattr(self, 'grid_selection_index'):
                    delattr(self, 'grid_selection_index')
                self.fill_grid_with_items()
                self.update_page_indicator()
                self.update_info_display()
                self.update_favourite_button_state()
    
    def prev_soundfont_page(self):
        if hasattr(self, 'current_grid_items') and hasattr(self, 'current_page'):
            if self.current_page > 0:
                self.current_page -= 1
                if hasattr(self, 'grid_selection_index'):
                    delattr(self, 'grid_selection_index')
                self.fill_grid_with_items()
                self.update_page_indicator()
                self.update_info_display()
                self.update_favourite_button_state()

    def next_grid_cell(self):
        if not hasattr(self, 'current_grid_items') or not self.current_grid_items:
            return
            
        if not hasattr(self, 'grid_selection_index'):
            self.grid_selection_index = 0
        else:
            available_grid_cells = 12
            start_idx = self.current_page * available_grid_cells
            end_idx = min(start_idx + available_grid_cells, len(self.current_grid_items))
            page_items_count = end_idx - start_idx
            
            self.grid_selection_index += 1
            
            if self.grid_selection_index >= page_items_count:
                if self.current_page < self.total_pages - 1:
                    self.next_soundfont_page()
                    self.grid_selection_index = 0
                else:
                    self.grid_selection_index = page_items_count - 1
        
        self.highlight_grid_selection()

    def prev_grid_cell(self):
        if not hasattr(self, 'current_grid_items') or not self.current_grid_items:
            return
            
        if not hasattr(self, 'grid_selection_index'):
            self.grid_selection_index = 0
        else:
            self.grid_selection_index -= 1
            
            if self.grid_selection_index < 0:
                if self.current_page > 0:
                    self.prev_soundfont_page()
                    available_grid_cells = 12
                    start_idx = self.current_page * available_grid_cells
                    end_idx = min(start_idx + available_grid_cells, len(self.current_grid_items))
                    page_items_count = end_idx - start_idx
                    self.grid_selection_index = page_items_count - 1
                else:
                    self.grid_selection_index = 0
        
        self.highlight_grid_selection()

    def highlight_grid_selection(self):
        if not hasattr(self, 'grid_selection_index'):
            return
            
        for i, button in enumerate(self.grid_buttons):
            if button['state'] == 'normal':
                button.config(
                    bg=zynthian_gui_config.color_panel_bg,
                    fg=zynthian_gui_config.color_panel_tx
                )
        
        if (hasattr(self, 'grid_selection_index') and 
            0 <= self.grid_selection_index < len(self.grid_buttons) and
            self.grid_buttons[self.grid_selection_index]['state'] == 'normal'):
            
            self.grid_buttons[self.grid_selection_index].config(
                bg=zynthian_gui_config.color_ctrl_bg_on,
                fg=zynthian_gui_config.color_ctrl_tx
            )
            
            self.main_frame.after(100, self.update_favourite_button_state)

    def select_current_grid_cell(self):
        if (hasattr(self, 'grid_selection_index') and 
            0 <= self.grid_selection_index < len(self.grid_buttons)):
            
            button = self.grid_buttons[self.grid_selection_index]
            if hasattr(button, 'grid_item') and button.grid_item:
                self.grid_button_click(self.grid_selection_index)
                return True
        return False

    def update_page_indicator(self):
        if hasattr(self, 'total_pages') and self.total_pages > 1:
            if hasattr(self, 'set_select_path'):
                self.set_select_path()
        
    def set_select_path(self):
        if self.processor:
            base_path = ""
            
            if hasattr(self, 'current_directory_info') and self.current_directory_info:
                base_path = f"Browse > {self.current_subdirectory} > {self.current_directory_info['name']}"
            else:
                if hasattr(self, 'current_subdirectory'):
                    base_path = f"Browse > {self.current_subdirectory}"
                else:
                    if self.processor.show_fav_presets:
                        base_path = self.processor.get_basepath() + " > Favorites"
                    else:
                        base_path = self.processor.get_bankpath()
            if hasattr(self, 'total_pages') and self.total_pages > 1:
                base_path += f"  [{self.current_page+1}/{self.total_pages}]"
            self.select_path.set(base_path)

    def select_action(self, index, t='S'):
        if t == 'S':
            if self.processor and index < len(self.list_data):
                preset_info = self.list_data[index]
                result = self.processor.set_preset(index)
                if result == "SOUNDFONT_LOADED":
                    self.fill_list()
                    if hasattr(self.processor, 'refresh_controllers'):
                        self.processor.refresh_controllers()
                    self.show_current_presets_in_grid()

    def switch_select(self, t='S'):
        if t == 'S':
            if self.select_current_grid_cell():
                return True
        return super().switch_select(t)

    def switch(self, swi, t='S'):
        if swi == 1 and t == 'S':
            if self.select_current_dir_cell():
                return True
            elif self.back_navigation():
                return True
        return super().switch(swi, t)

    def show(self):
        if self.processor:
            super().show()
            self.index = -1
            self.set_selector(zs_hidden=False)
            if hasattr(self, 'full_container'):
                self.full_container.tkraise()
            self.set_select_path()
            self.load_subdirectory_contents()
            self.fill_directory_navigation()
            self.update_info_display()
            self.main_frame.update_idletasks()
            
            if self.current_subdirectory != "Favourite" and self.all_directories:
                if len(self.all_directories) > 0:
                    self.dir_nav_click(1)
            elif self.current_subdirectory == "Favourite":
                self.fill_list()
        else:
            super().show()
            self.index = -1
            if hasattr(self, 'full_container'):
                self.full_container.tkraise()
            self.set_select_path()
            error_items = [{
                'name': "No processor available",
                'preset_info': None,
                'display_text': "No processor available for grid preset interface",
                'type': 'message'
            }]
            self.display_items_in_grid(error_items)

    def hide(self):
        self.stop_text_scrolling()
        if hasattr(self, 'subdir_dropdown') and self.subdir_dropdown:
            self.subdir_dropdown.destroy()
            self.subdir_dropdown = None
        super().hide()

    def send_controller_value(self, zctrl):
        if not self.shown:
            return
        if zctrl == self.zselector.zctrl:
            index = zctrl.value
            if 0 <= index < len(self.list_data):
                self.index = index
                self.update_selection_highlight()
        elif hasattr(super(), 'send_controller_value'):
            super().send_controller_value(zctrl)

    def handle_dir_page_button_click(self, direction):
        """Handle clicks on directory page navigation buttons"""
        if direction == 'prev':
            self.prev_dir_page()
        elif direction == 'next':
            self.next_dir_page()

    def update_info_display(self):
        """Update the info display in row 4 with current soundfont and preset information"""
        if not (hasattr(self, 'preset_info_label') and hasattr(self, 'soundfont_info_label')):
            return
            
        preset_name = ""
        if self.processor:
            preset_info = getattr(self.processor, 'preset_info', None)
            if preset_info and len(preset_info) > 2 and preset_info[2]:
                preset_name = preset_info[2]
                if preset_name.startswith("❤"):
                    preset_name = preset_name[1:]
        self.preset_info_label.config(text=preset_name)
        
        soundfont_name = ""
        if self.processor:
            if hasattr(self.processor, 'bank_info') and self.processor.bank_info and self.processor.bank_info[0]:
                bank_path = self.processor.bank_info[0]
                if os.path.isfile(bank_path):
                    soundfont_filename = os.path.basename(bank_path)
                    soundfont_name = os.path.splitext(soundfont_filename)[0].replace('_', ' ')
            elif hasattr(self.processor, 'preset_info') and self.processor.preset_info and len(self.processor.preset_info) > 0:
                preset_path = self.processor.preset_info[0]
                if os.path.isfile(preset_path):
                    soundfont_filename = os.path.basename(preset_path)
                    soundfont_name = os.path.splitext(soundfont_filename)[0].replace('_', ' ')
        
        self.soundfont_info_label.config(text=soundfont_name)
        
        self.update_favourite_button_state()

    def toggle_favourite(self):
        """Toggle favourite status of current preset using Zynthian's standard favorite system"""
        current_preset = self.get_current_preset()
        
        if not current_preset:
            logging.warning("No current preset to toggle favorite")
            return
            
        try:
            self.processor.toggle_preset_fav(current_preset)
            logging.info(f"Toggled favorite for preset: {current_preset[2]}")
            
            if self.current_subdirectory == "Favourite":
                self.load_favourite_directories()
                self.fill_list()
            
            self.update_favourite_button_state()
            
        except Exception as e:
            logging.error(f"Error toggling favorite: {e}")

    def get_current_preset(self):
        """Get the current preset info in a consistent way"""
        current_preset = None
        
        if (hasattr(self, 'grid_selection_index') and 
            self.grid_selection_index is not None and 
            0 <= self.grid_selection_index < len(self.grid_buttons)):
            
            button = self.grid_buttons[self.grid_selection_index]
            if (hasattr(button, 'grid_item') and 
                button.grid_item and 
                button.grid_item['type'] == 'soundfont'):
                current_preset = button.grid_item['preset_info']
                return current_preset
        
        if self.processor:
            if hasattr(self.processor, 'preset_info') and self.processor.preset_info:
                current_preset = self.processor.preset_info
                return current_preset
            
            if (hasattr(self.processor, 'preset_name') and self.processor.preset_name and
                hasattr(self.processor, 'bank_info') and self.processor.bank_info):
                
                current_preset = [
                    self.processor.bank_info[0],
                    0,
                    self.processor.preset_name,
                    'soundfont',
                    os.path.basename(self.processor.bank_info[0]) if self.processor.bank_info[0] else ""
                ]
                return current_preset
        
        return None

    def is_preset_favourite(self, preset_info):
        """Check if preset is in favourites using Zynthian's standard favorite system"""
        if not preset_info or not self.processor:
            return False
            
        try:
            return self.processor.engine.is_preset_fav(preset_info)
        except Exception as e:
            logging.error(f"Error checking if preset is favorite: {e}")
            return False

    def load_favourite_directories(self):
        """Load favorite presets using Zynthian's standard favorite system"""
        try:
            self.all_directories = []
            self.favourite_soundfonts = []
            
            if self.processor:
                fav_presets = self.processor.get_preset_favs()
                
                if fav_presets:
                    for preset_id, preset_data in fav_presets.items():
                        if preset_data and len(preset_data) >= 2:
                            bank_info = preset_data[0]
                            preset_info = preset_data[1]
                            
                            if (bank_info and len(bank_info) >= 1 and 
                                preset_info and len(preset_info) >= 1):
                                soundfont_path = preset_info[0]
                                
                                if soundfont_path and os.path.exists(soundfont_path):
                                    if soundfont_path not in self.favourite_soundfonts:
                                        self.favourite_soundfonts.append(soundfont_path)
                
                if self.favourite_soundfonts:
                    self.all_directories.append({
                        'name': 'Favourite',
                        'path': 'Favourite',
                        'display_name': 'Favourite',
                        'type': 'directory'
                    })
                    
        except Exception as e:
            logging.error(f"Error loading favourite directories: {e}")

    def update_favourite_button_state(self):
        """Update favourite button appearance based on current preset status"""
        if not hasattr(self, 'favourite_canvas') or not self.processor:
            return
            
        try:
            current_preset = self.get_current_preset()
            
            if current_preset and self.is_preset_favourite(current_preset):
                self.favourite_canvas.after(10, lambda: self.draw_star_button(is_favourite=True))
            else:
                self.favourite_canvas.after(10, lambda: self.draw_star_button(is_favourite=False))
                
        except Exception as e:
            logging.error(f"Error updating favourite button state: {e}")
            self.favourite_canvas.after(10, lambda: self.draw_star_button(is_favourite=False))

    def on_subdirectory_change(self, selection):
        self.current_subdirectory = selection
        if hasattr(self, 'current_directory_info'):
            delattr(self, 'current_directory_info')
        if hasattr(self, 'grid_selection_index'):
            delattr(self, 'grid_selection_index')
        self.index = -1
        self.load_subdirectory_contents()
        self.fill_directory_navigation()
        self.current_dir_page = 0
        self.dir_selection_index = 1
        self.set_select_path()
        self.highlight_dir_selection()
        if self.current_subdirectory == "Favourite":
            self.fill_list()
        else:
            if self.all_directories:
                self.dir_nav_click(1)
            else:
                self.fill_list()
                self.auto_select_soundfont_in_current_directory()

    def auto_select_soundfont_in_current_directory(self):
        if self.current_subdirectory == "Favourite":
            return
        if not (hasattr(self, 'current_directory_info') and self.current_directory_info):
            return
        current_soundfont_path = None
        if hasattr(self.processor, 'preset_info') and self.processor.preset_info:
            current_soundfont_path = self.processor.preset_info[0] if self.processor.preset_info[0] else None
        elif hasattr(self.processor, 'bank_info') and self.processor.bank_info:
            current_soundfont_path = self.processor.bank_info[0] if self.processor.bank_info[0] else None
        if not current_soundfont_path or not hasattr(self, 'list_data'):
            return
        current_dir_path = self.current_directory_info['path']
        if not current_soundfont_path.startswith(current_dir_path):
            return
        highlight_index = next((i for i, item in enumerate(self.list_data) if item[0] == current_soundfont_path), -1)
        if highlight_index >= 0:
            available_grid_cells = 12
            target_page = highlight_index // available_grid_cells
            target_position = highlight_index % available_grid_cells
            if target_page != self.current_page:
                self.current_page = target_page
                self.fill_grid_with_items()
            self.grid_selection_index = target_position
            self.highlight_grid_selection()

    def load_subdirectory_contents(self):
        """Load contents based on selected subdirectory"""
        if not hasattr(self, 'current_subdirectory'):
            self.current_subdirectory = "SD/User"
        self.all_directories = []
        if self.current_subdirectory == "SD/User":
            user_dir = "/zynthian/zynthian-my-data/soundfonts/sf2"
            if os.path.exists(user_dir):
                self.scan_directory_for_subdirs(user_dir, "User")
        elif self.current_subdirectory == "SD/System":
            system_dir = "/zynthian/zynthian-data/soundfonts/sf2"
            if os.path.exists(system_dir):
                self.scan_directory_for_subdirs(system_dir, "System")
        elif self.current_subdirectory == "USB":
            usb_dirs = self.get_usb_directories()
            for usb_dir in usb_dirs:
                self.scan_directory_for_subdirs(usb_dir, "USB")
        elif self.current_subdirectory == "Favourite":
            self.load_favourite_directories()

    def scan_directory_for_subdirs(self, base_dir, prefix):
        try:
            subdirs_with_soundfonts = []
            for item in sorted(os.listdir(base_dir)):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path) and self.directory_contains_soundfonts(item_path):
                    subdirs_with_soundfonts.append({
                        'name': f"{prefix}/{item}",
                        'path': item_path,
                        'display_name': item[:10] if len(item) > 10 else item,
                        'type': 'directory'
                    })
            
            if subdirs_with_soundfonts:
                self.all_directories.extend(subdirs_with_soundfonts)
            elif self.directory_contains_soundfonts(base_dir):
                dir_name = os.path.basename(base_dir)
                display_name = "System" if prefix == "System" else (dir_name[:10] if len(dir_name) > 10 else dir_name)
                self.all_directories.append({
                    'name': f"{prefix}",
                    'path': base_dir,
                    'display_name': display_name,
                    'type': 'directory'
                })
            else:
                dir_name = os.path.basename(base_dir)
                display_name = "System" if prefix == "System" else (dir_name[:10] if len(dir_name) > 10 else dir_name)
                self.all_directories.append({
                    'name': f"{prefix}",
                    'path': base_dir,
                    'display_name': display_name,
                    'type': 'directory'
                })
        except Exception:
            pass
    def directory_contains_soundfonts(self, directory_path):
        try:
            for item in os.listdir(directory_path):
                if item.lower().endswith(('.sf2', '.sf3')):
                    return True
            for item in os.listdir(directory_path):
                if item.startswith('.'):
                    continue
                item_path = os.path.join(directory_path, item)
                if os.path.isdir(item_path):
                    if self.directory_contains_soundfonts(item_path):
                        return True
            return False
        except Exception:
            return False

    def get_usb_directories(self):
        """Get USB directories from /media/root/ with automatic name detection"""
        usb_dirs = []
        try:
            usb_base = "/media/root"
            if os.path.exists(usb_base):
                for item in os.listdir(usb_base):
                    item_path = os.path.join(usb_base, item)
                    if os.path.isdir(item_path):
                        if self.is_usb_device(item_path):
                            usb_dirs.append(item_path)
        except Exception as e:
            logging.error(f"Error getting USB directories: {e}")
        return usb_dirs
    
    def is_usb_device(self, path):
        """Check if a path is likely a USB device"""
        try:
            if path in ['/media/root/.', '/media/root/..']:
                return False
            
            if os.listdir(path):
                return True
                
            return False
        except Exception:
            return False

    def draw_star_button(self, is_favourite=False):
        """Draw star shape using turtle-inspired algorithm on canvas"""
        if not hasattr(self, 'favourite_canvas'):
            return
            
        self.favourite_canvas.delete("all")
        
        canvas_width = self.favourite_canvas.winfo_width()
        canvas_height = self.favourite_canvas.winfo_height()
        
        if canvas_width <= 1:
            canvas_width = 80
        if canvas_height <= 1:
            canvas_height = 40
            
        center_x = canvas_width // 2
        center_y = canvas_height // 2
        radius = int(min(canvas_width, canvas_height) // 5)
        
        points = []
        angle = -90
        
        for i in range(5):
            x = center_x + radius * math.cos(math.radians(angle))
            y = center_y + radius * math.sin(math.radians(angle))
            points.extend([x, y])
            
            angle += 36
            x = center_x + (radius * 0.4) * math.cos(math.radians(angle))
            y = center_y + (radius * 0.4) * math.sin(math.radians(angle))
            points.extend([x, y])
            
            angle += 36
        
        if is_favourite:
            self.favourite_canvas.create_polygon(
                points,
                fill=zynthian_gui_config.color_ctrl_tx,
                outline=zynthian_gui_config.color_ctrl_tx,
                width=1
            )
        else:
            self.favourite_canvas.create_polygon(
                points,
                fill="",
                outline=zynthian_gui_config.color_panel_tx,
                width=2
            )