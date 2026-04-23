import sys
import time
import wave
import threading
import warnings
import numpy as np
import sounddevice as sd
import whisper
from pynput import keyboard as pkeyboard
from pynput.keyboard import Controller as KeyboardController

warnings.filterwarnings("ignore")

'''
https://github.com/openai/whisper
Size      Parameters  English-only model  Multilingual model  Required VRAM  Relative speed
tiny      39 M        tiny.en             tiny                ~1 GB          ~10x
base      74 M        base.en             base                ~1 GB          ~7x
small     244 M       small.en            small               ~2 GB          ~4x
medium    769 M       medium.en           medium              ~5 GB          ~2x
large     1550 M      N/A                 large               ~10 GB         1x
turbo     809 M       N/A                 turbo               ~6 GB          ~8x
'''
model = whisper.load_model("base.en")

### CONSTANTS ###
SAMPLE_RATE     = 44100
CHANNELS        = 1
BITS_PER_SAMPLE = 16
CHUNK_MS        = 100
CHUNK_FRAMES    = SAMPLE_RATE * CHUNK_MS // 1000
OUTPUT_FILE     = "recording.wav"
##########################################

### Keyboard controller for text output ###
kb = KeyboardController()

### Hotkey state (Ctrl + Cmd = record) ###
held_keys = set()

def on_press(key):
    held_keys.add(key)

def on_release(key):
    held_keys.discard(key)

# NOTE: macOS requires Accessibility permissions for the Listener to work.
# Go to System Settings → Privacy & Security → Accessibility and add your terminal.
key_listener = pkeyboard.Listener(on_press=on_press, on_release=on_release)
key_listener.start()

def keys_held():
    ctrl  = any(k in held_keys for k in (pkeyboard.Key.ctrl, pkeyboard.Key.ctrl_l, pkeyboard.Key.ctrl_r))
    space = pkeyboard.Key.space in held_keys
    return ctrl and space


def type_text(text, interval=0.01):
    for char in text:
        kb.type(char)
        time.sleep(interval)
##########################################

### Get the current audio input devices ###
devices = sd.query_devices()
input_devices = [(i, d['name']) for i, d in enumerate(devices) if d['max_input_channels'] > 0]

print("Enter the ID for your audio device:")
for idx, name in input_devices:
    print(f"ID={idx}, {name}")
device_index = int(input("Enter ID: "))
##########################################

### Audio capture via sounddevice ###
pcm_chunks = []
recording   = False
lock        = threading.Lock()

def audio_callback(indata, frames, time_info, status):
    if recording:
        with lock:
            pcm_chunks.append(indata.copy())

stream = sd.InputStream(
    device=device_index,
    samplerate=SAMPLE_RATE,
    channels=CHANNELS,
    dtype='int16',
    callback=audio_callback,
    blocksize=CHUNK_FRAMES,
)
stream.start()
##########################################

### Recording/Typing Logic ###
print("Hold Ctrl+Space to record")

while True:
    held = keys_held()

    # idle → recording
    if held and not recording:
        recording = True
        with lock:
            pcm_chunks = []
        print("Recording...")

    # recording → idle
    elif not held and recording:
        recording = False

        with lock:
            chunks = list(pcm_chunks)
            pcm_chunks = []

        if chunks:
            pcm_data = np.concatenate(chunks, axis=0)
            with wave.open(OUTPUT_FILE, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(BITS_PER_SAMPLE // 8)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm_data.tobytes())

            result = model.transcribe(OUTPUT_FILE)
            fixed_text = result["text"]
            if fixed_text and fixed_text[0] == " ":
                fixed_text = fixed_text[1:]

            type_text(fixed_text)

    time.sleep(0.01)
