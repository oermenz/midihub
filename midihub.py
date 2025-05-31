#!/usr/bin/env python3

import subprocess
import time
import re
import os
import sys
import logging
import datetime

LOCKFILE = "/tmp/midihub_debounce.lock"
DEBOUNCE_SECONDS = 2
TRIGGER_FILE = "/tmp/midihub_devices.trigger"

# --- LOGGING (optional, can be removed if not needed) ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# ==== MIDI LOGIC (unchanged) ====
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

# ==== AUDIO ROUTING (JACK) ====
def ensure_jack_installed():
    try:
        import jack  # noqa: F401
        return True
    except ImportError:
        logging.warning("python-jack-client not installed; skipping audio routing.")
        return False

def ensure_jack_running(server_name='default', sample_rate=48000, buffer_size=256):
    try:
        import jack
        client = jack.Client('midihub_probe', no_start_server=True)
        return True
    except Exception:
        # Try to start JACK
        jackd_cmd = [
            'jackd',
            '-d', 'alsa',
            '-r', str(sample_rate),
            '-p', str(buffer_size),
            '-n', '2'
        ]
        logging.info(f"Starting JACK server: {' '.join(jackd_cmd)}")
        subprocess.Popen(jackd_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Wait for JACK to start
        for _ in range(20):
            try:
                import jack
                client = jack.Client('midihub_probe', no_start_server=True)
                return True
            except Exception:
                time.sleep(0.5)
        logging.error("Failed to start JACK server.")
        return False

def get_physical_ports_by_device(client):
    # JACK 'system' ports are used for physical I/O
    capture_ports = [p for p in client.get_ports(is_physical=True, is_output=True, is_audio=True) if p.name.startswith('system:')]
    playback_ports = [p for p in client.get_ports(is_physical=True, is_input=True, is_audio=True) if p.name.startswith('system:')]

    def group_ports(ports):
        grouped = []
        port_names = [p.name for p in ports]
        for i in range(0, len(port_names), 2):
            group = port_names[i:i+2]
            if len(group) == 2:
                grouped.append(group)
        return grouped

    return group_ports(capture_ports), group_ports(playback_ports)

def connect_all_to_all_stereo(client):
    captures, playbacks = get_physical_ports_by_device(client)
    for i, playback in enumerate(playbacks):
        for j, capture in enumerate(captures):
            if i == j:
                continue  # skip self-loop
            try:
                client.connect(playback[0], capture[0])
                client.connect(playback[1], capture[1])
                logging.info(f"Connected AUDIO: {playback} → {capture}")
            except Exception as e:
                logging.warning(f"AUDIO connection error: {playback} → {capture}: {e}")

def run_audio_autorouter():
    if not ensure_jack_installed():
        return
    if not ensure_jack_running():
        logging.error("JACK not running; cannot route audio.")
        return
    import jack
    client = jack.Client('midihub_router')
    connect_all_to_all_stereo(client)
    client.close()

# ==== MAIN LOGIC ====
def main():
    recently_triggered()
    disconnect_all_midi()
    ports, names = get_midi_ports()
    connect_all_ports(ports)
    # --- Audio routing ---
    try:
        run_audio_autorouter()
    except Exception as e:
        logging.warning(f"Audio routing failed: {e}")
    notify_device_change()
    logging.info("All MIDI ports connected, audio routed, and device change notified.")
    sys.exit(0)

if __name__ == "__main__":
    main()
