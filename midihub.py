#!/usr/bin/env python3

import subprocess
import time
import re
import os

LOCKFILE = "/tmp/midihub_debounce.lock"
DEBOUNCE_SECONDS = 2

def recently_triggered():
    if os.path.exists(LOCKFILE):
        last = os.path.getmtime(LOCKFILE)
        if time.time() - last < DEBOUNCE_SECONDS:
            # Exit if the script was triggered too recently
            exit(0)
    with open(LOCKFILE, "w") as f:
        f.write(str(time.time()))

recently_triggered()

TRIGGER_FILE = "/tmp/midihub_devices.trigger"

def notify_device_change():
    with open(TRIGGER_FILE, 'w') as f:
        f.write(str(time.time()))

def run_command(command):
    return subprocess.check_output(command, shell=True, text=True)

def disconnect_all_midi():
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
    return ports, names

def connect_all_ports(ports):
    for i, p1 in enumerate(ports):
        for j, p2 in enumerate(ports):
            if i != j:
                subprocess.call(f"aconnect {p1}:0 {p2}:0", shell=True)

def main():
    disconnect_all_midi()
    ports, names = get_midi_ports()
    connect_all_ports(ports)
    notify_device_change()

if __name__ == "__main__":
    main()
