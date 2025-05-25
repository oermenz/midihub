#!/usr/bin/env python3

import subprocess
import re
import os

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

def show_on_oled(names):
    cmd = "/usr/local/bin/midioled.py"
    if len(names) > 1:
        args = " ".join([repr(name) for name in names])
    else:
        args = "'' 'No MIDI' 'connections'"
    subprocess.Popen(f"{cmd} {args}", shell=True)

def main():
    disconnect_all_midi()
    ports, names = get_midi_ports()
    connect_all_ports(ports)
    show_on_oled(names)

if __name__ == "__main__":
    main()
