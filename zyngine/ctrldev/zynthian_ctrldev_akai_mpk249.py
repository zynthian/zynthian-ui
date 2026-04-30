# /zynthian/zynthian-ui/zyngine/ctrldev/zynthian_ctrldev_akai_mpk249.py

import jack

class zynthian_ctrldev_akai_mpk249:
    dev_ids = ["AKAI MPK249", "MPK249 IN 1"]
    driver_name = "zynthian_ctrldev_akai_mpk249"
    driver_description = "Zynthian Control Device for AKAI MPK249"

    def __init__(self, state_manager):
        self.state_manager = state_manager

        # Initialize MIDI input and output
        try:
            self.midi_in = jack.Client(self.driver_name + "_in")
            self.midi_out = jack.Client(self.driver_name + "_out")
        except Exception as e:
            print(f"Failed to initialize Jack client: {e}")
            return

        # Connect to the first available MIDI ports
        in_ports = [port for port in self.midi_in.get_ports(is_output=True)]
        out_ports = [port for port in self.midi_out.get_ports(is_input=True)]

        if in_ports and out_ports:
            try:
                self.midi_in.connect(in_ports[0], out_ports[0])
            except Exception as e:
                print(f"Failed to connect ports: {e}")
                return

        # Register a callback function
        self.midi_in.set_process_callback(self.on_midi_message)

    def get_driver_name(cls):
        return cls.driver_name

    @classmethod
    def get_autoload_flag(cls):
        return True

    def on_midi_message(self, frames_per_buffer):
        for i in range(frames_per_buffer):
            event = self.midi_in.get_next_event()
            if event:
                message, time = event
                self.process_midi_message(message)

    def process_midi_message(self, message):
        status, data1, data2 = message
        if status == 0x90:  # Note On
            print(f"Note On: {data1}, Velocity: {data2}")
        elif status == 0x80:  # Note Off
            print(f"Note Off: {data1}, Velocity: {data2}")
        elif status == 0xB0:  # Control Change
            if data1 == 0x01:
                print(f"Modulation Wheel: Value: {data2}")
            elif data1 == 0x07:
                print(f"Volume: Value: {data2}")
            elif data1 == 0x0A:
                print(f"PAN: Value: {data2}")
            # Add more mappings as needed based on the MIDI map file
