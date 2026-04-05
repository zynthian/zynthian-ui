#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ****************************************************************************
# Zynthian Control Device Driver for SINCO SMK25
#
# All 8 knobs configured via the 25KEY editor with Left=0, Right=1,
# so they send only CC values 0 (CCW) and 1 (CW).
#
# Knobs 1–4 (CC 20–23): ZYNPOT 0–3 (screen encoders)
# Knob 5   (CC 24):     Arrow Left / Right
# Knob 6   (CC 25):     Arrow Up / Down
# Knob 7   (CC 26):     Preset previous / next
# Knob 8   (CC 27):     BACK (CCW) / SELECT (CW)
# Knob 9   (CC 28):     Admin (CCW) / Menu (CW)
#
# Transport buttons (CC Single, Channel 1, Value 1):
# PLAY  (CC 102):  Toggle Play
# STOP  (CC 103):  Stop
# REC   (CC 104):  Toggle Record
#
# Pads (CC Toggle, Channel 10):
# Top row   (CC 105–112): Solo toggle for chains 0–7
# Bottom row (CC 89–96):  Mute toggle for chains 0–7
#
# Copyright (C) 2024 The SMK Project Contributors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ****************************************************************************

import logging
import threading
from time import time, sleep

import dbus

from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynmixer
from zyngine.zynthian_signal_manager import zynsigman
from zyncoder.zyncore import lib_zyncore

# ---------------------------------------------------------------------------
# Knob CC mapping — all on MIDI channel 0 (wire channel 1)
# ---------------------------------------------------------------------------

KNOB_MIDI_CHANNEL = 0x00
PAD_MIDI_CHANNEL = 0x09    # Pads send on MIDI channel 10 (drum channel)

# Top row: CC → zynpot index
ZYNPOT_KNOBS = {20: 0, 21: 1, 22: 2, 23: 3}

# Bottom row CCs
CC_ARROW_LR = 24   # Knob 5
CC_ARROW_UD = 25   # Knob 6
CC_PRESET   = 26   # Knob 7
CC_SEL_BACK = 27   # Knob 8
CC_OPT_ADMIN = 28  # Knob 9

# All knob CCs for quick membership test
ALL_KNOB_CCS = {20, 21, 22, 23, 24, 25, 26, 27, 28}

# Transport button CCs (CC Single, channel 0, value 1 on press)
CC_PLAY = 102
CC_STOP = 103
CC_REC  = 104
TRANSPORT_CCS = {CC_PLAY, CC_STOP, CC_REC}

# Pad CC ranges (CC Toggle mode, set in 25KEY editor)
SOLO_PAD_CCS = range(105, 113)    # Top row: CC 105–112
MUTE_PAD_CCS = range(89, 97)      # Bottom row: CC 89–96
ALL_PAD_CCS  = set(SOLO_PAD_CCS) | set(MUTE_PAD_CCS)

# Debounce interval (seconds) for SELECT/BACK knob
SEL_BACK_DEBOUNCE = 0.6

# ---------------------------------------------------------------------------
# Flash / SysEx protocol constants for pad LED control
# ---------------------------------------------------------------------------

FLASH_TYPE = 0x05           # FlashType for data writes
PRESET_STRIDE = 0x1DA       # Bytes between preset blocks in flash
PAD_STRIDE = 8              # Bytes per pad entry
PAD_BASE_ADDR = 0x150       # Flash base of pad data
DEFAULT_PRESET = 7          # Device preset index (UI "Preset 8")
FLASH_BASE = PAD_BASE_ADDR + (DEFAULT_PRESET * PRESET_STRIDE)  # 0xE1E
RGB_OFFSET = 5              # Bytes 5,6,7 within each 8-byte pad entry

# Pad layout per bank: (function, chain_index, cc_number)
# Bank 1: chains 0,1,2 + master(7)  —  Bank 2: chains 3,4,5,6
# Within each bank: pads 0-3 = top row (solo), pads 4-7 = bottom row (mute)
BANK1_PAD_MAP = [
    ('solo', 0, 105), ('solo', 1, 106), ('solo', 2, 107), ('solo', 7, 112),
    ('mute', 0, 89),  ('mute', 1, 90),  ('mute', 2, 91),  ('mute', 7, 96),
]
BANK2_PAD_MAP = [
    ('solo', 3, 108), ('solo', 4, 109), ('solo', 5, 110), ('solo', 6, 111),
    ('mute', 3, 92),  ('mute', 4, 93),  ('mute', 5, 94),  ('mute', 6, 95),
]

# Bank offsets within preset pad area
BANK1_OFFSET = 0x00
BANK2_OFFSET = 0x40

# CC number → (bank_offset, pad_index, function, chain_index) for fast lookup
_CC_TO_PAD = {}
for _idx, (_func, _chain, _cc) in enumerate(BANK1_PAD_MAP):
    _CC_TO_PAD[_cc] = (BANK1_OFFSET, _idx, _func, _chain)
for _idx, (_func, _chain, _cc) in enumerate(BANK2_PAD_MAP):
    _CC_TO_PAD[_cc] = (BANK2_OFFSET, _idx, _func, _chain)

# Pad LED colors (R, G, B)
COLOR_OFF      = (0, 0, 0)         # LED off — no chain at this position
COLOR_SOLO_ON  = (124, 184, 90)    # Granola
COLOR_SOLO_OFF = (0, 40, 40)       # Dim cyan
COLOR_MUTE_ON  = (255, 0, 0)       # Bright red
COLOR_MUTE_OFF = (40, 0, 40)       # Dim purple

# BLE GATT vendor characteristic UUID for flash writes
GATT_CHAR_UUID = "0000ae41-0000-1000-8000-00805f9b34fb"
GATT_DEVICE_PATH = "/org/bluez/hci0/dev_00_AC_87_D3_C2_25"

# Inter-packet delay (seconds)
GATT_WRITE_DELAY = 0.02
PAD_WRITE_DELAY = 0.02
PRESET_WRITE_DELAY = 0.03    # Delay between chunks when writing full preset

# Preset data builder constants
BTN_STRIDE = 0x46           # Bytes per transport button entry
KNOB_ENTRY_SIZE = 6         # Bytes per knob entry

FLASH_TYPE_4 = 0x04         # FlashType for device config / preset switching


# ---------------------------------------------------------------------------
# Driver class
# ---------------------------------------------------------------------------

class zynthian_ctrldev_sinco_smk25_bt(zynthian_ctrldev_zynmixer):
    """Zynthian control device driver for the SINCO SMK25.

    All 8 knobs are set to range 0–1 via the 25KEY editor, producing
    CC value 0 (CCW) or 1 (CW) — effectively relative encoders.

    Top row  (CC 20–23): ZYNPOT 0–3
    Bottom row:
      CC 24  Arrow Left / Right
      CC 25  Arrow Up / Down
      CC 26  Preset previous / next
      CC 27  BACK (CCW) / SELECT (CW)
      CC 28  Admin (CCW) / Menu (CW)
    Transport buttons:
      CC 102  Toggle Play
      CC 103  Stop
      CC 104  Toggle Record
    Pads (CC Toggle, channel 10):
      Top row   (CC 105–112): Solo for chains 0–7
      Bottom row (CC 89–96):  Mute for chains 0–7
    """

    dev_ids = ["SMK25V2 IN"]
    driver_name = "SINCO SMK25 Bluetooth"
    driver_description = "SMK25: knobs + transport + mute/solo pads"

    # Over BLE, keyboard notes and control CCs share a single MIDI port.
    # Don't block MIDI from reaching chains — midi_event() already consumes
    # control CCs (returns True) and passes keyboard notes through (returns False).
    unroute_from_chains = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, state_manager, idev_in, idev_out=None):
        self.last_sel_back_time = 0
        self._gatt_char = None
        self._led_dirty = threading.Event()
        self._led_stop = threading.Event()
        self._led_worker = None
        super().__init__(state_manager, idev_in, idev_out)

    def init(self):
        # Find the BLE GATT characteristic for flash writes
        self._gatt_char = self._find_gatt_char()
        self._led_lock = threading.Lock()
        super().init()
        # Write our desired preset configuration to the device
        threading.Thread(
            target=self._write_preset_config,
            name="smk25-bt-preset-config",
            daemon=True,
        ).start()
        # Start persistent LED worker thread
        self._led_stop.clear()
        self._led_worker = threading.Thread(
            target=self._led_worker_loop,
            name="smk25-led-worker",
            daemon=True,
        )
        self._led_worker.start()
        zynsigman.register_queued(
            zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self.on_screen_change)

    def end(self):
        self._led_stop.set()
        self._led_dirty.set()  # Wake worker so it can exit
        if self._led_worker and self._led_worker.is_alive():
            self._led_worker.join(timeout=5.0)
        zynsigman.unregister(
            zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self.on_screen_change)
        super().end()

    def refresh(self, *args, **kwargs):
        """Called when screen changes or chains are modified."""
        self._led_dirty.set()

    def _led_worker_loop(self):
        """Persistent worker: waits for dirty flag, then updates all pad LEDs."""
        while not self._led_stop.is_set():
            self._led_dirty.wait()
            if self._led_stop.is_set():
                break
            self._led_dirty.clear()
            self._update_pad_leds()

    def update_mixer_active_chain(self, active_chain):
        """Called by base class when active chain changes."""
        self._led_dirty.set()

    def update_mixer_strip(self, chan, symbol, value):
        """Called by base class when a mixer control changes (mute/solo/level).

        Attempts a fast single-pad write for the affected channel.
        Falls back to full update if no matching pad is found.
        """
        if symbol not in ('mute', 'solo'):
            return
        # Try to find the pad(s) for this mixer channel and write just those
        for bank_map, bank_offset in [(BANK1_PAD_MAP, BANK1_OFFSET), (BANK2_PAD_MAP, BANK2_OFFSET)]:
            for pad_idx, (func, chain_idx, cc_num) in enumerate(bank_map):
                if func != symbol:
                    continue
                if chain_idx == 7 and func == 'mute' and chan == 16:
                    self._write_single_pad_led(cc_num)
                    return
                chain = self.chain_manager.get_chain_by_position(chain_idx, midi=False)
                if chain and chain.mixer_chan == chan:
                    self._write_single_pad_led(cc_num)
                    return
        # Fallback: full update
        self._led_dirty.set()

    def on_screen_change(self, screen):
        """Respond to GUI screen changes."""
        self._led_dirty.set()

    # ------------------------------------------------------------------
    # MIDI event handler
    # ------------------------------------------------------------------

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        ev_chan = ev[0] & 0x0F

        # Only handle CC events
        if evtype != 0xB:
            return False

        cc_num = ev[1] & 0x7F
        cc_val = ev[2] & 0x7F

        # --- Pad CCs on channel 9 (MIDI channel 10) ---
        if ev_chan == PAD_MIDI_CHANNEL:
            if cc_num in ALL_PAD_CCS and cc_val > 0:
                self._handle_pad(cc_num)
            return True  # Consume all ch9 CC events

        # --- Knobs and transport on channel 0 ---
        if ev_chan != KNOB_MIDI_CHANNEL:
            return False

        # --- Transport buttons ---
        if cc_num in TRANSPORT_CCS and cc_val > 0:
            if cc_num == CC_PLAY:
                self.state_manager.send_cuia("TOGGLE_PLAY")
            elif cc_num == CC_STOP:
                self.state_manager.send_cuia("STOP")
            elif cc_num == CC_REC:
                self.state_manager.send_cuia("TOGGLE_RECORD")
            return True

        if cc_num not in ALL_KNOB_CCS:
            return False

        # All knobs: 0 = CCW (−1), ≥1 = CW (+1)
        delta = 1 if cc_val >= 1 else -1

        # --- Top row: ZYNPOT 0–3 ---
        zynpot_index = ZYNPOT_KNOBS.get(cc_num)
        if zynpot_index is not None:
            self.state_manager.send_cuia("ZYNPOT", [zynpot_index, delta])
            return True

        # --- Bottom row ---
        if cc_num == CC_ARROW_LR:
            self.state_manager.send_cuia("ARROW_RIGHT" if delta > 0 else "ARROW_LEFT")
            return True

        if cc_num == CC_ARROW_UD:
            self.state_manager.send_cuia("ARROW_DOWN" if delta > 0 else "ARROW_UP")
            return True

        if cc_num == CC_PRESET:
            try:
                chain = self.state_manager.chain_manager.get_active_chain()
                if chain and chain.current_processor:
                    processor = chain.current_processor
                    if hasattr(processor, 'preset_list') and processor.preset_list:
                        current_index = processor.preset_index if hasattr(processor, 'preset_index') else 0
                        new_index = (current_index + delta) % len(processor.preset_list)
                        processor.set_preset(new_index)
                        self.state_manager.send_cuia("refresh_screen", ["control"])
                        self.state_manager.send_cuia("refresh_screen", ["audio_mixer"])
            except Exception as e:
                logging.warning(f"SMK25 preset browse error: {e}")
            return True

        if cc_num == CC_SEL_BACK:
            now = time()
            if now - self.last_sel_back_time < SEL_BACK_DEBOUNCE:
                return True
            self.last_sel_back_time = now
            if delta > 0:
                self.state_manager.send_cuia("ZYNSWITCH", [3, 'S'])
            else:
                self.state_manager.send_cuia("BACK")
            return True

        if cc_num == CC_OPT_ADMIN:
            if delta > 0:
                self.state_manager.send_cuia("MENU")
            else:
                self.state_manager.send_cuia("SCREEN_ADMIN")
            return True

        return False

    # ------------------------------------------------------------------
    # Pad handling — mute / solo
    # ------------------------------------------------------------------

    def _handle_pad(self, cc_num):
        """Toggle solo (CC 105–112) or mute (CC 89–96) for the chain."""
        try:
            if cc_num in SOLO_PAD_CCS:
                track = cc_num - 105  # CC 105–112 → tracks 0–7
                chain = self.chain_manager.get_chain_by_position(track, midi=False)
                if chain and chain.mixer_chan is not None and chain.mixer_chan < 16:
                    cur = self.zynmixer.get_solo(chain.mixer_chan)
                    self.zynmixer.set_solo(chain.mixer_chan, 0 if cur else 1)

            elif cc_num in MUTE_PAD_CCS:
                track = cc_num - 89  # CC 89–96 → tracks 0–7
                if track < 7:
                    chain = self.chain_manager.get_chain_by_position(track, midi=False)
                    if chain and chain.mixer_chan is not None and chain.mixer_chan < 16:
                        cur = self.zynmixer.get_mute(chain.mixer_chan)
                        self.zynmixer.set_mute(chain.mixer_chan, 0 if cur else 1)
                else:
                    # Last pad (CC 96) = master mute (mixer channel 16)
                    cur = self.zynmixer.get_mute(16)
                    self.zynmixer.set_mute(16, 0 if cur else 1)

            # Write LED immediately — CC Momentary has no hardware LED toggle
            self._write_single_pad_led(cc_num)

        except Exception as e:
            logging.warning(f"SMK25 pad error: {e}")

    # ------------------------------------------------------------------
    # Pad LED control
    # ------------------------------------------------------------------

    def _pad_color(self, func, chain_idx):
        """Return (R, G, B) for a pad based on chain existence and mute/solo state.

        Returns COLOR_OFF if no chain exists at chain_idx (except master/chain 7
        which always shows for mute).
        """
        # Master channel (index 7) — always exists for mute
        if chain_idx == 7:
            if func == 'mute':
                return COLOR_MUTE_ON if self.zynmixer.get_mute(16) else COLOR_MUTE_OFF
            else:
                # No solo for master
                return COLOR_OFF

        chain = self.chain_manager.get_chain_by_position(chain_idx, midi=False)
        if not chain or chain.mixer_chan is None or chain.mixer_chan >= 16:
            return COLOR_OFF

        if func == 'solo':
            return COLOR_SOLO_ON if self.zynmixer.get_solo(chain.mixer_chan) else COLOR_SOLO_OFF
        else:
            return COLOR_MUTE_ON if self.zynmixer.get_mute(chain.mixer_chan) else COLOR_MUTE_OFF

    def _write_single_pad_led(self, cc_num):
        """Fast-path: write only the affected pad's RGB + pad 0 RGB + commit.

        Writes only 3 bytes (R,G,B) at pad_addr+5, preserving the
        pad's CC/type/channel config.
        """
        if self._gatt_char is None:
            return
        info = _CC_TO_PAD.get(cc_num)
        if info is None:
            return
        if not self._led_lock.acquire(blocking=False):
            return

        try:
            bank_offset, pad_idx, func, chain_idx = info
            r, g, b = self._pad_color(func, chain_idx)

            addr = FLASH_BASE + bank_offset + (pad_idx * PAD_STRIDE) + RGB_OFFSET
            self._write_flash(addr, bytes([r, g, b]))
            sleep(PAD_WRITE_DELAY)

            # Write pad 0 RGB last to trigger LED refresh
            if not (bank_offset == BANK1_OFFSET and pad_idx == 0):
                pad0_func, pad0_chain, _ = BANK1_PAD_MAP[0]
                pad0_r, pad0_g, pad0_b = self._pad_color(pad0_func, pad0_chain)
                pad0_addr = FLASH_BASE + BANK1_OFFSET + RGB_OFFSET
                self._write_flash(pad0_addr, bytes([pad0_r, pad0_g, pad0_b]))
                sleep(PAD_WRITE_DELAY)

            self._commit_flash(FLASH_BASE)

        except Exception as e:
            logging.warning(f"SMK25 single pad LED error: {e}")
        finally:
            self._led_lock.release()

    def _update_pad_leds(self):
        """Write pad LED colors reflecting current mute/solo state.

        Writes only 3 RGB bytes per pad (at offset +5) to preserve the
        pad's CC/type/channel config.  Pad 0 (bank 1) must be written
        last before commit to trigger the LED refresh.
        """
        if self._gatt_char is None:
            return
        if not self._led_lock.acquire(blocking=False):
            return  # Another update is already in progress

        try:
            bank1_entries = []
            bank2_entries = []

            for bank_map, bank_offset, entries in [
                (BANK1_PAD_MAP, BANK1_OFFSET, bank1_entries),
                (BANK2_PAD_MAP, BANK2_OFFSET, bank2_entries),
            ]:
                for pad_idx, (func, chain_idx, cc_num) in enumerate(bank_map):
                    r, g, b = self._pad_color(func, chain_idx)
                    addr = FLASH_BASE + bank_offset + (pad_idx * PAD_STRIDE) + RGB_OFFSET
                    entries.append((addr, bytes([r, g, b])))

            # Write bank 1 pads 1-7, then all bank 2, then bank 1 pad 0 last
            for addr, rgb in bank1_entries[1:]:
                self._write_flash(addr, rgb)
                sleep(PAD_WRITE_DELAY)

            for addr, rgb in bank2_entries:
                self._write_flash(addr, rgb)
                sleep(PAD_WRITE_DELAY)

            # Pad 0 must be written last before commit
            addr, rgb = bank1_entries[0]
            self._write_flash(addr, rgb)
            sleep(PAD_WRITE_DELAY)

            self._commit_flash(FLASH_BASE)

        except Exception as e:
            logging.warning(f"SMK25 LED update error: {e}")
        finally:
            self._led_lock.release()

    # ------------------------------------------------------------------
    # Flash preset configuration
    # ------------------------------------------------------------------

    def _write_preset_config(self):
        """Write the complete Zynthian preset to preset 8 (index 7) on the device.

        This eliminates the need for the MidiSuite app — the driver programs
        the controller directly via BLE GATT on every startup.
        """
        if self._gatt_char is None:
            logging.warning("SMK25 BT: no GATT char — skipping preset config")
            return

        sleep(1.5)  # Let the device settle after BLE connection

        preset_data = _build_preset_data()
        flash_addr = DEFAULT_PRESET * PRESET_STRIDE  # Preset 8 = index 7

        logging.info(f"SMK25 BT: writing {len(preset_data)}-byte preset to flash "
                     f"addr 0x{flash_addr:04X} (preset {DEFAULT_PRESET + 1})")

        try:
            # Write in 0x40-byte (64-byte) chunks
            chunk_size = 0x40
            for offset in range(0, len(preset_data), chunk_size):
                chunk = preset_data[offset:offset + chunk_size]
                self._write_flash(flash_addr + offset, chunk)
                sleep(PRESET_WRITE_DELAY)

            self._commit_flash(flash_addr)
            logging.info("SMK25 BT: preset config written successfully")

            # Switch to the preset we just wrote
            self._switch_preset(DEFAULT_PRESET)
            sleep(1.5)  # Let device settle after preset switch
            self._update_pad_leds()  # Write LED colors now that preset is active
        except Exception as e:
            logging.warning(f"SMK25 BT: preset config write failed: {e}")

    def _switch_preset(self, preset_idx=DEFAULT_PRESET):
        """Switch the device to the given preset live (0-indexed).

        Requires two "primer" messages followed by FlashType 4
        writes to offsets 0x00-0x0A with the preset index, then a
        FlashType 4 commit.  Discovered via binary-search testing.
        """
        if self._gatt_char is None:
            logging.warning("SMK25 BT: no GATT char — skipping preset switch")
            return

        try:
            # Primer messages (required to unlock live preset switch)
            self._gatt_write(_build_raw_packet(bytes([0x00, 0x59, preset_idx])))
            self._gatt_write(_build_raw_packet(bytes([0x00, 0x59, 0x22, preset_idx])))
            sleep(0.2)

            # FlashType 4 writes at even offsets 0x00-0x0A
            for offset in range(0x00, 0x0C, 0x02):
                raw = _build_ft4_write_packet(offset, bytes([preset_idx, 0x00]))
                self._gatt_write(raw)
                sleep(0.03)

            # FlashType 4 commit
            raw = _build_ft4_commit_packet()
            self._gatt_write(raw)
            logging.info(f"SMK25 BT: switched to preset {preset_idx + 1}")
        except Exception as e:
            logging.warning(f"SMK25 BT: preset switch failed: {e}")

    # ------------------------------------------------------------------
    # BLE GATT flash write helpers
    # ------------------------------------------------------------------

    def _find_gatt_char(self):
        """Find the vendor GATT characteristic (0xae41) via BlueZ D-Bus."""
        try:
            bus = dbus.SystemBus()
            om = dbus.Interface(
                bus.get_object("org.bluez", "/"),
                "org.freedesktop.DBus.ObjectManager",
            )
            objects = om.GetManagedObjects()
            for path, ifaces in objects.items():
                if not path.startswith(GATT_DEVICE_PATH):
                    continue
                props = ifaces.get("org.bluez.GattCharacteristic1")
                if not props:
                    continue
                if str(props.get("UUID", "")) == GATT_CHAR_UUID:
                    char = dbus.Interface(
                        bus.get_object("org.bluez", path),
                        "org.bluez.GattCharacteristic1",
                    )
                    logging.info(f"SMK25 BT: found GATT char {GATT_CHAR_UUID} at {path}")
                    return char
        except Exception as e:
            logging.warning(f"SMK25 BT: GATT discovery error: {e}")
        logging.warning("SMK25 BT: GATT characteristic not found")
        return None

    def _gatt_write(self, raw_packet):
        """Write raw packet to vendor GATT characteristic."""
        self._gatt_char.WriteValue(list(raw_packet), {"type": "command"})
        sleep(GATT_WRITE_DELAY)

    def _write_flash(self, addr, data):
        """Send a flash-write packet for data at addr via GATT."""
        raw = _build_write_packet(addr, data)
        self._gatt_write(raw)

    def _commit_flash(self, addr=0):
        """Send the flash commit packet via GATT."""
        raw = _build_commit_packet(addr)
        self._gatt_write(raw)


# ---------------------------------------------------------------------------
# Pure-function protocol helpers (no instance state needed)
# ---------------------------------------------------------------------------

def _build_write_packet(addr, data):
    """Build a raw flash-write packet (pre-encoding).

    Layout: [0x00, 0x59, 0x22, size_LE×3, FlashType, addr_LE×4,
             data_len_LE×3, *data, checksum]
    """
    data_len = len(data)
    size = data_len + 8

    header = bytes([
        0x00, 0x59, 0x22,
        size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF,
    ])
    body = bytes([
        FLASH_TYPE,
        addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF, (addr >> 24) & 0xFF,
        data_len & 0xFF, (data_len >> 8) & 0xFF, (data_len >> 16) & 0xFF,
    ]) + bytes(data)

    cs = (~sum(body)) & 0xFF
    return header + body + bytes([cs])


def _build_commit_packet(addr=0):
    """Build the flash save/commit packet (write with data_len=0)."""
    body = bytes([
        FLASH_TYPE,
        addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF, (addr >> 24) & 0xFF,
        0, 0, 0,
    ])
    cs = (~sum(body)) & 0xFF
    return bytes([0x00, 0x59, 0x22, 8, 0, 0]) + body + bytes([cs])


def _build_raw_packet(raw_payload):
    """Wrap a raw payload for GATT write (no 7-bit encoding over BLE)."""
    return raw_payload


def _build_ft4_write_packet(addr, data):
    """Build a FlashType 4 write packet (for preset switching)."""
    data_len = len(data)
    size = data_len + 8
    header = bytes([
        0x00, 0x59, 0x22,
        size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF,
    ])
    body = bytes([
        FLASH_TYPE_4,
        addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF, (addr >> 24) & 0xFF,
        data_len & 0xFF, (data_len >> 8) & 0xFF, (data_len >> 16) & 0xFF,
    ]) + bytes(data)
    cs = (~sum(body)) & 0xFF
    return header + body + bytes([cs])


def _build_ft4_commit_packet(addr=0):
    """Build the FlashType 4 commit packet."""
    body = bytes([
        FLASH_TYPE_4,
        addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF, (addr >> 24) & 0xFF,
        0, 0, 0,
    ])
    cs = (~sum(body)) & 0xFF
    return bytes([0x00, 0x59, 0x22, 8, 0, 0]) + body + bytes([cs])


# ---------------------------------------------------------------------------
# Preset data builder — constructs the 474-byte preset blob
# ---------------------------------------------------------------------------

def _build_preset_data():
    """Build the 474-byte preset blob for the Zynthian SMK25 configuration.

    This produces the exact same data as the Loadtopreset8inmidisuite.mkc
    file, constructed programmatically from the driver constants so the
    mapping is always in sync.

    Preset layout (474 = 0x1DA bytes):
      0x000    4   Global flags
      0x004    1   Pitch bend range
      0x005   25   Keyboard note offsets
      0x01E   70x3 Transport buttons (PLAY, STOP, REC)
      0x0F0   48   Knob page 1 (8 knobs)
      0x120   48   Knob page 2 (8 knobs)
      0x150   64   Pad bank 1 (8 pads)
      0x190   64   Pad bank 2 (8 pads)
      0x1D0   10   Tail settings
    """
    buf = bytearray(PRESET_STRIDE)  # 474 bytes, zero-filled

    # --- Global header (0x000-0x004) ---
    buf[0x04] = 0x7F  # Pitch bend range = 127 (full)

    # --- Keyboard note offsets (0x005-0x01D) ---
    for i in range(25):
        buf[0x05 + i] = i

    # --- Transport buttons (3 x 70 bytes starting at 0x01E) ---
    transport_buttons = [
        (CC_PLAY, 1),   # CC 102, value 1
        (CC_STOP, 1),   # CC 103, value 1
        (CC_REC,  1),   # CC 104, value 1
    ]
    for btn_idx, (cc, val) in enumerate(transport_buttons):
        base = 0x01E + btn_idx * BTN_STRIDE
        buf[base + 2] = cc
        buf[base + 3] = val

    # --- Knob page 1 (0x0F0): 8 knobs x 6 bytes ---
    knob_page1 = [
        (0x03, 0x02, 0x00, 20, 0, 1),   # Knob 1: ZYNPOT 0
        (0x03, 0x02, 0x00, 21, 0, 1),   # Knob 2: ZYNPOT 1
        (0x03, 0x02, 0x00, 22, 0, 1),   # Knob 3: ZYNPOT 2
        (0x03, 0x02, 0x00, 23, 0, 1),   # Knob 4: ZYNPOT 3
        (0x03, 0x00, 0x00, 24, 0, 1),   # Knob 5: Arrow L/R
        (0x03, 0x00, 0x00, 25, 0, 1),   # Knob 6: Arrow U/D
        (0x03, 0x00, 0x00, 26, 0, 1),   # Knob 7: Preset prev/next
        (0x03, 0x00, 0x00, 27, 0, 1),   # Knob 8: BACK / SELECT
    ]
    for i, (ktype, speed, ch, cc, left, right) in enumerate(knob_page1):
        off = 0x0F0 + i * KNOB_ENTRY_SIZE
        buf[off:off + 6] = bytes([ktype, speed, ch, cc, left, right])

    # --- Knob page 2 (0x120): 8 knobs x 6 bytes ---
    knob_page2 = [
        (0x03, 0x01, 0x00, 28, 0, 1),   # Knob 9:  Admin / Menu
        (0x00, 0x02, 0x00, 29, 0, 127), # Knob 10: CC 29 pass-through
        (0x00, 0x02, 0x00, 30, 0, 127), # Knob 11: CC 30 pass-through
        (0x03, 0x02, 0x00, 27, 0, 1),   # Knob 12: BACK / SELECT (dup)
        (0x03, 0x00, 0x00, 28, 0, 1),   # Knob 13: Admin / Menu (dup)
        (0x03, 0x00, 0x00, 25, 0, 1),   # Knob 14: Arrow U/D (dup)
        (0x00, 0x00, 0x00, 46, 0, 127), # Knob 15: CC 46 pass-through
        (0x03, 0x00, 0x00, 27, 0, 1),   # Knob 16: BACK / SELECT (dup)
    ]
    for i, (ktype, speed, ch, cc, left, right) in enumerate(knob_page2):
        off = 0x120 + i * KNOB_ENTRY_SIZE
        buf[off:off + 6] = bytes([ktype, speed, ch, cc, left, right])

    # --- Pad bank 1 (0x150): 8 pads x 8 bytes ---
    for i, (func, chain_idx, cc_num) in enumerate(BANK1_PAD_MAP):
        off = 0x150 + i * PAD_STRIDE
        buf[off:off + 5] = bytes([0x02, 0x09, cc_num, 0x00, 0x7F])

    # --- Pad bank 2 (0x190): 8 pads x 8 bytes ---
    for i, (func, chain_idx, cc_num) in enumerate(BANK2_PAD_MAP):
        off = 0x190 + i * PAD_STRIDE
        buf[off:off + 5] = bytes([0x02, 0x09, cc_num, 0x00, 0x7F])

    # --- Tail (0x1D0): 10 bytes ---
    buf[0x1D2] = 0x01   # Velocity curve = 1
    buf[0x1D4] = 0x7F   # Max velocity = 127
    buf[0x1D7] = 0x40   # Aftertouch sensitivity = 64
    buf[0x1D9] = 0x7F   # Pitch bend range = 127

    return bytes(buf)
