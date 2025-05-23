import time
import threading
from mido import MidiInput, MidiOutput, get_input_names, get_output_names, open_input, open_output
import mido
from pydbus import SystemBus
from gi.repository import GLib
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont

# --- OLED setup ---
import board
import busio

i2c = busio.I2C(board.SCL, board.SDA)
oled = SSD1306_I2C(128, 32, i2c)

font = ImageFont.load_default()

# --- Globals ---
last_ch = 0
last_cc = 0
last_val = 0
last_note = ""
bpm = 0

# MIDI Fighter Twister device name (change if needed)
MFT_NAME = "Midi Fighter Twister"

# MIDI Clock BPM calculator
class MidiClockBPM:
    def __init__(self):
        self.tick_times = []
        self.bpm = 0

    def clock_tick(self):
        now = time.time()
        self.tick_times.append(now)
        # Keep last 24 ticks (~1 bar at 24 ppqn)
        if len(self.tick_times) > 24:
            self.tick_times.pop(0)
            delta = self.tick_times[-1] - self.tick_times[0]
            if delta > 0:
                # MIDI clock sends 24 pulses per quarter note
                self.bpm = 60 / (delta / 24)
        return self.bpm

bpm_calc = MidiClockBPM()

# --- Bluetooth MIDI pairing handler ---
class BluetoothMidiPairer:
    def __init__(self):
        self.bus = SystemBus()
        self.adapter_path = None
        self.adapter = None
        self.find_adapter()

    def find_adapter(self):
        mngr = self.bus.get('org.bluez', '/')
        objects = mngr.GetManagedObjects()
        for path, interfaces in objects.items():
            if 'org.bluez.Adapter1' in interfaces:
                self.adapter_path = path
                self.adapter = self.bus.get('org.bluez', path)
                break

    def start_discovery(self):
        if self.adapter:
            self.adapter.StartDiscovery()

    def stop_discovery(self):
        if self.adapter:
            self.adapter.StopDiscovery()

    def pair_device(self, device_path):
        device = self.bus.get('org.bluez', device_path)
        try:
            device.Pair()
        except Exception as e:
            print(f"Pairing failed: {e}")

    def trust_device(self, device_path):
        device = self.bus.get('org.bluez', device_path)
        try:
            device.Trust()
        except Exception as e:
            print(f"Trust failed: {e}")

# --- MIDI handling ---
class MidiHub:
    def __init__(self):
        self.in_ports = []
        self.out_ports = []
        self.running = True
        self.bpm = 0

        # For display info
        self.last_ch = 0
        self.last_cc = 0
        self.last_val = 0
        self.last_note = ""

        # Open ports and store references
        self.open_ports()

    def open_ports(self):
        input_names = get_input_names()
        output_names = get_output_names()
        self.in_ports = []
        self.out_ports = []

        # Open all inputs
        for name in input_names:
            try:
                port = open_input(name)
                self.in_ports.append(port)
            except:
                pass

        # Open all outputs
        for name in output_names:
            try:
                port = open_output(name)
                self.out_ports.append((name, port))
            except:
                pass

    def send_message(self, msg):
        # Send to all outputs except MFT for inputs
        for name, port in self.out_ports:
            if MFT_NAME in name:
                # MFT should NOT receive midi (only send)
                continue
            try:
                port.send(msg)
            except:
                pass

    def send_to_mft(self, msg):
        # Only send to MFT device
        for name, port in self.out_ports:
            if MFT_NAME in name:
                try:
                    port.send(msg)
                except:
                    pass

    def midi_loop(self):
        while self.running:
            for port in self.in_ports:
                for msg in port.iter_pending():
                    self.handle_message(msg)
            time.sleep(0.001)

    def handle_message(self, msg):
        # Process MIDI Clock for BPM
        if msg.type == 'clock':
            self.bpm = bpm_calc.clock_tick()

        # Update display info for CC and Note On messages
        if msg.type == 'control_change':
            self.last_ch = msg.channel + 1
            self.last_cc = msg.control
            self.last_val = msg.value

        elif msg.type == 'note_on':
            self.last_ch = msg.channel + 1
            self.last_note = self.note_name(msg.note)

            # Also send LED dimming CC to MFT for the note-to-encoder mapping here if needed
            # Example placeholder - implement mapping logic here if desired

        # Forward the message to outputs (except MFT)
        self.send_message(msg)

    def note_name(self, note):
        # Convert MIDI note number to name with octave
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (note // 12) - 1
        name = notes[note % 12]
        return f"{name}{octave}"

    def stop(self):
        self.running = False
        for port in self.in_ports:
            port.close()
        for _, port in self.out_ports:
            port.close()

# --- OLED display updater ---
class DisplayUpdater:
    def __init__(self, midi_hub):
        self.midi_hub = midi_hub
        self.width = 128
        self.height = 32
        self.image = Image.new('1', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)

    def update_display(self):
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        # Top line: CH, CC, VAL
        top_line = f"CH:{self.midi_hub.last_ch} CC:{self.midi_hub.last_cc} VAL:{self.midi_hub.last_val}"
        # Bottom line: NOTE, BPM
        bpm_str = f"{self.midi_hub.bpm:.1f}" if self.midi_hub.bpm > 0 else "---"
        bottom_line = f"NOTE:{self.midi_hub.last_note} BPM:{bpm_str}"
        self.draw.text((0, 0), top_line, font=font, fill=255)
        self.draw.text((0, 16), bottom_line, font=font, fill=255)
        oled.image(self.image)
        oled.show()

    def run(self):
        while True:
            self.update_display()
            time.sleep(0.2)

# --- Main program ---
def main():
    midi_hub = MidiHub()
    display = DisplayUpdater(midi_hub)

    # Start MIDI processing thread
    midi_thread = threading.Thread(target=midi_hub.midi_loop, daemon=True)
    midi_thread.start()

    # Start display updater thread
    display_thread = threading.Thread(target=display.run, daemon=True)
    display_thread.start()

    # Bluetooth pairing setup (just discovery here, no button yet)
    bt_pairer = BluetoothMidiPairer()
    bt_pairer.start_discovery()
    print("Bluetooth discovery started")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        midi_hub.stop()
        bt_pairer.stop_discovery()

if __name__ == "__main__":
    main()
