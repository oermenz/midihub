#!/usr/bin/env python3

import subprocess
import logging
import fcntl
import time
import sys

# ==== CONFIGURATION ====
LOCKFILE = "/tmp/audioup_debounce.lock"
DEBOUNCE_SECONDS = 2

# --- LOGGING (optional, can be removed if not needed) ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

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
    # ==== DEBOUNCE LOGIC ====
    now = time.time()
    try:
        with open(LOCKFILE, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            ts = f.read().strip()
            if ts:
                try:
                    last = float(ts)
                except ValueError:
                    last = 0
            else:
                last = 0
            if now - last < DEBOUNCE_SECONDS:
                logging.info("Debounce: called too soon, exiting.")
                return
            f.seek(0)
            f.truncate()
            f.write(str(now))
            f.flush()
    except Exception as e:
        logging.warning(f"Debounce lock error: {e}")

    try:
        run_audio_autorouter()
        logging.info("Audio routed successfully.")
    except Exception as e:
        logging.warning(f"Audio routing failed: {e}")
    sys.exit(0)
