#!/usr/bin/env python3
import time
import mido
import board
import busio
import adafruit_ssd1306
from pydbus import SystemBus
from gi.repository import GLib
from threading import Thread
from PIL import Image, ImageDraw, ImageFont

# ---------------------- OLED SETUP ----------------------
WIDTH = 128
HEIGHT = 64
i2c = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)
oled.fill(0)
oled.show()

font = ImageFont.load_default()
image = Image.new("1", (WIDTH, HEIGHT))
draw = ImageDraw.Draw(image)

def display_message(top="", mid="", bot=""):
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=0, fill=0)
    draw.text((0, 0), top, font=font, fill=255)
    draw.text((0, 24), mid, font=font, fill=255)
    draw.text((0, 48), bot, font=font, fill=255)
    oled.image(image)
    oled.show()

# ---------------------- MIDI SETUP ----------------------
in_ports = [mido.open_input(name) for name in mido.get_input_names()]
out_ports = [mido.open_output(name) for name in mido.get_output_names()]

note_names = ['C', 'C#', 'D', 'D#', 'E', 'F',
              'F#', 'G', 'G#', 'A', 'A#', 'B']

def note_number_to_name(n):
    return f"{note_names[n % 12]}{n // 12 - 1}"

def handle_midi(msg):
    try:
        if msg.type in ('note_on', 'note_off', 'control_change'):
            ch = msg.channel + 1
            cc = getattr(msg, 'control', '-') if hasattr(msg, 'control') else '-'
            val = getattr(msg, 'value', '-') if hasattr(msg, 'value') else '-'
            note = note_number_to_name(msg.note) if hasattr(msg, 'note') else '-'

            display_message(f"CH:{ch} CC:{cc} VAL:{val} NOTE:{note}",
                            f"{msg.type.upper()}",
                            f"{msg}")
        for out in out_ports:
            out.send(msg)
    except Exception as e:
        display_message("MIDI Error", str(e), "")

def midi_loop():
    while True:
        for port in in_ports:
            for msg in port.iter_pending():
                handle_midi(msg)
        time.sleep(0.001)

# ---------------------- BLUETOOTH SETUP ----------------------
def setup_bt_agent():
    class NoInputNoOutputAgent:
        def Release(self): pass
        def RequestPinCode(self, device): return ''
        def RequestPasskey(self, device): return dbus.UInt32(0)
        def RequestConfirmation(self, device, passkey): return True
        def RequestAuthorization(self, device): return True
        def AuthorizeService(self, device, uuid): return True
        def Cancel(self): pass

    bus = SystemBus()
    adapter_path = '/org/bluez/hci0'
    bluez = bus.get('org.bluez', '/org/bluez')
    adapter = bus.get('org.bluez', adapter_path)

    adapter.Powered = True
    adapter.Discoverable = True
    adapter.Pairable = True

    agent_path = "/test/agent"
    obj = bus.get("org.bluez", "/org/bluez")
    manager = bus.get("org.bluez", "/org/bluez")

    from pydbus.generic import signal
    from pydbus.generic import Property
    from pydbus import Variant

    class Agent:
        def Release(self): pass
        def RequestPinCode(self, device): return "0000"
        def RequestPasskey(self, device): return dbus.UInt32(0)
        def DisplayPasskey(self, device, passkey, entered): pass
        def RequestConfirmation(self, device, passkey): return True
        def AuthorizeService(self, device, uuid): return True
        def Cancel(self): pass

    bus.register_object(agent_path, Agent(),
                        None)

    agent_manager = bus.get("org.bluez", "/org/bluez")
    agent_manager.RegisterAgent(agent_path, "NoInputNoOutput")
    agent_manager.RequestDefaultAgent(agent_path)

    display_message("Bluetooth", "Agent registered", "Waiting for pairing...")

# ---------------------- MAIN ----------------------
if __name__ == "__main__":
    try:
        display_message("Starting MIDI Hub", "BT Agent + MIDI", "")
        setup_bt_agent()

        t = Thread(target=midi_loop)
        t.start()

        GLib.MainLoop().run()

    except KeyboardInterrupt:
        display_message("Shutting down...", "", "")
        time.sleep(1)
        oled.fill(0)
        oled.show()
