#!/usr/bin/env python3

import subprocess
import time
import re
import os
import sys
import logging

LOCKFILE = "/tmp/midihub_debounce.lock"
DEBOUNCE_SECONDS = 2
TRIGGER_FILE = "/tmp/midihub_devices.trigger"

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

def recently_triggered():
    if os.path.exists(LOCKFILE):
        last = os.path.getmtime(LOCKFILE)
        if time.time() - last < DEBOUNCE_SECONDS:
            logging.info("Debounced: Script triggered too recently.")
            sys.exit(0)
    with open(LOCKFILE, "w") as f:
        f.write(str(time.time()))

def notify_device_change():
    try:
        with open(TRIGGER_FILE, 'w') as f:
            f.write(str(time.time()))
        logging.info(f"Device change notified via trigger file: {TRIGGER_FILE}")
    except Exception as e:
        logging.error(f"Failed to write trigger file: {e}")

def run_command(command):
    try:
        output = subprocess.check_output(command, shell=True, text=True)
        return output
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to run command '{command}': {e}")
        sys.exit(1)

def disconnect_all_midi():
    logging.info("Disconnecting all MIDI ports...")
    subprocess.call("aconnect -x", shell=True)

def get_midi_ports():
    output = run_command("aconnect -i -l")
    ports = []
    names = []
    for line in output.splitlines():
        match = re.search(r"client (\d+): '([^']+)'", line)
        if match:
            port = match.group(1)
            name = match.group(2)
            if port != "0" and "Through" not in name:
                ports.append(port)
                names.append(name)
    if not ports:
        logging.warning("No MIDI ports found.")
    else:
        logging.info(f"Found MIDI ports: {names}")
    return ports, names

def connect_all_ports(ports):
    n = len(ports)
    if n < 2:
        logging.info("Not enough MIDI ports to connect.")
        return
    logging.info("Connecting all MIDI ports bidirectionally (no redundancies)...")
    for i in range(n):
        for j in range(i + 1, n):
            src, dst = ports[i], ports[j]
            # Connect both directions, once each
            logging.info(f"Connecting {src}:0 -> {dst}:0")
            subprocess.call(f"aconnect {src}:0 {dst}:0", shell=True)
            logging.info(f"Connecting {dst}:0 -> {src}:0")
            subprocess.call(f"aconnect {dst}:0 {src}:0", shell=True)

def main():
    recently_triggered()
    disconnect_all_midi()
    ports, names = get_midi_ports()
    connect_all_ports(ports)
    notify_device_change()
    logging.info("All MIDI ports connected and device change notified.")
    sys.exit(0)

if __name__ == "__main__":
    main()
