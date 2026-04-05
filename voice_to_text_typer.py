import ctypes
import ctypes.wintypes
import subprocess

### Prevent CMD from briefly popping up (it gets annoying) ###
_original_popen = subprocess.Popen

class SilentPopen(_original_popen):
    def __init__(self, *args, **kwargs):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs.setdefault("startupinfo", startupinfo)
        super().__init__(*args, **kwargs)

subprocess.Popen = SilentPopen
##########################################

import sys
import time
import wave
import whisper
import warnings
warnings.filterwarnings("ignore")

'''
https://github.com/openai/whisper
Size      Parameters  English-only model	Multilingual model	Required VRAM	Relative speed
tiny      39 M        tiny.en             tiny	              ~1 GB	        ~10x
base      74 M        base.en             base	              ~1 GB	        ~7x
small     244 M       small.en            small	              ~2 GB	        ~4x
medium    769 M       medium.en           medium	            ~5 GB	        ~2x
large     1550 M	    N/A                 large	              ~10 GB	      1x
turbo     809 M       N/A	                turbo	              ~6 GB	        ~8x
'''
model = whisper.load_model("base.en")

### CONSTANTS ###
# ── winmm constants ──
WAVE_FORMAT_PCM  = 0x0001
CALLBACK_NULL    = 0x00000000
MMSYSERR_NOERROR = 0
WHDR_DONE        = 0x00000001
 
# ── keyboard virtual-key codes ──
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LWIN     = 0x5B
VK_RWIN     = 0x5C
 
# ── audio settings ──
SAMPLE_RATE     = 44100
CHANNELS        = 1
BITS_PER_SAMPLE = 16
CHUNK_MS        = 100  # ms per buffer — longer = more time to harvest
NUM_BUFFERS     = 4  # number of rotating buffers
CHUNK_FRAMES    = SAMPLE_RATE * CHUNK_MS // 1000
CHUNK_BYTES     = CHUNK_FRAMES * CHANNELS * (BITS_PER_SAMPLE // 8)
OUTPUT_FILE     = "recording.wav"

# ── keyboard settings ──
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
##########################################

# ── DLLs ──
winmm  = ctypes.WinDLL("winmm")
user32 = ctypes.WinDLL("user32")
kernel32 = ctypes.WinDLL("kernel32")

### Define structs for Windows API calls ###
class WAVEINCAPS(ctypes.Structure):
    _fields_ = [
        ("wMid",           ctypes.c_uint16),
        ("wPid",           ctypes.c_uint16),
        ("vDriverVersion", ctypes.c_uint32),
        ("szPname",        ctypes.c_char * 32),
        ("dwFormats",      ctypes.c_uint32),
        ("wChannels",      ctypes.c_uint16),
        ("wReserved1",     ctypes.c_uint16),
    ]

class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag",      ctypes.c_uint16),
        ("nChannels",       ctypes.c_uint16),
        ("nSamplesPerSec",  ctypes.c_uint32),
        ("nAvgBytesPerSec", ctypes.c_uint32),
        ("nBlockAlign",     ctypes.c_uint16),
        ("wBitsPerSample",  ctypes.c_uint16),
        ("cbSize",          ctypes.c_uint16),
    ]

DWORD_PTR = ctypes.c_uint64 if sys.maxsize > 2**32 else ctypes.c_uint32
class WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData",          ctypes.c_void_p),   # LPSTR
        ("dwBufferLength",  ctypes.c_uint32),   # DWORD
        ("dwBytesRecorded", ctypes.c_uint32),   # DWORD
        ("dwUser",          DWORD_PTR),         # DWORD_PTR
        ("dwFlags",         ctypes.c_uint32),   # DWORD
        ("dwLoops",         ctypes.c_uint32),   # DWORD
        ("lpNext",          ctypes.c_void_p),   # struct wavehdr_tag*
        ("reserved",        DWORD_PTR),         # DWORD_PTR
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT),
        ("padding", ctypes.c_ubyte * 8),  # aligns to 28 bytes on 64-bit
    ]
##########################################

### Functions ###
def keys_held():
    ctrl = (user32.GetAsyncKeyState(VK_LCONTROL) & 0x8000) or \
           (user32.GetAsyncKeyState(VK_RCONTROL) & 0x8000)
    win  = (user32.GetAsyncKeyState(VK_LWIN)     & 0x8000) or \
           (user32.GetAsyncKeyState(VK_RWIN)      & 0x8000)
    return bool(ctrl and win) 


def type_text(text, interval=0.01):
    for char in text:
        code = ord(char)

        # Key down
        down = INPUT(type=INPUT_KEYBOARD,
                     ki=KEYBDINPUT(wScan=code, dwFlags=KEYEVENTF_UNICODE))
        res = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        # Key up
        up = INPUT(type=INPUT_KEYBOARD,
                   ki=KEYBDINPUT(wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))

        time.sleep(interval)
##########################################

### Get the current audio devices ###       
count = winmm.waveInGetNumDevs()

devices = []
for i in range(count):
    caps = WAVEINCAPS()
    winmm.waveInGetDevCapsA(i, ctypes.byref(caps), ctypes.sizeof(caps))
    devices.append((i, caps.szPname.decode("utf-8", errors="replace")))
print("Enter the ID for your audio device:")
for i in range(0,count):
    print("ID=" + str(devices[i][0]) + ", " + devices[i][1])
device_index = 0
device_index = int(input("Enter ID: "))
##########################################

### Open the selected audio device ###  
hwi = ctypes.c_void_p()
wfx = WAVEFORMATEX()
wfx.wFormatTag      = WAVE_FORMAT_PCM
wfx.nChannels       = CHANNELS
wfx.nSamplesPerSec  = SAMPLE_RATE
wfx.wBitsPerSample  = BITS_PER_SAMPLE
wfx.nBlockAlign     = CHANNELS * (BITS_PER_SAMPLE // 8)
wfx.nAvgBytesPerSec = SAMPLE_RATE * wfx.nBlockAlign
wfx.cbSize          = 0

ret = winmm.waveInOpen(
            ctypes.byref(hwi),
            ctypes.c_uint(device_index),
            ctypes.byref(wfx),
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
            ctypes.c_uint(CALLBACK_NULL),
        )

raw_buffers = []
headers     = []

for i in range(NUM_BUFFERS):
    # Allocate the PCM data buffer and pin it in raw_buffers.
    buf = ctypes.create_string_buffer(CHUNK_BYTES)
    raw_buffers.append(buf)

    hdr = WAVEHDR()
    hdr.lpData = ctypes.addressof(buf)  # pointer to our PCM memory
    hdr.dwBufferLength = CHUNK_BYTES
    hdr.dwFlags = 0

    ret = winmm.waveInPrepareHeader(
        hwi,  # HWAVEIN
        ctypes.byref(hdr),  # LPWAVEHDR
        ctypes.sizeof(hdr),  # UINT (size of the header struct)
    )
    headers.append(hdr)

# ── queue all buffers ──
for i, hdr in enumerate(headers):
    ret = winmm.waveInAddBuffer(
        hwi,
        ctypes.byref(hdr),
        ctypes.sizeof(hdr),
    )
##########################################

### Recording/Typing Logic ###  
pcm_chunks  = []
recording   = False

print("Hold Ctrl+Win to record")

while True:
    held = keys_held()

    # idle → recording
    if held and not recording:
        recording = True
        pcm_chunks = []
        winmm.waveInStart(hwi)
        print("Recording...")

    # recording → idle
    elif not held and recording:
        recording = False
        winmm.waveInStop(hwi)

        # drain any buffers the driver just finished
        for hdr in headers:
            if hdr.dwFlags & WHDR_DONE and hdr.dwBytesRecorded > 0:
                pcm_chunks.append(ctypes.string_at(hdr.lpData, hdr.dwBytesRecorded))

        # save wav
        if pcm_chunks:
            pcm_data = b"".join(pcm_chunks)
            with wave.open(OUTPUT_FILE, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(BITS_PER_SAMPLE // 8)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm_data)
            #print(f"Saved {len(pcm_data)} bytes to {OUTPUT_FILE}")
            start_time = time.time()
            result = model.transcribe("recording.wav")
            #print(result["text"])
            end_time = time.time()
            #print("time:", end_time-start_time)

            ### fix the text ###
            fixed_text = result["text"]
            # remove space at start
            if(fixed_text[0] == " "):
                fixed_text = fixed_text[1:]

            type_text(fixed_text)

    # collect completed buffers while recording
    if recording:
        for i, hdr in enumerate(headers):
            if not (hdr.dwFlags & WHDR_DONE):
                continue

            pcm_chunks.append(ctypes.string_at(hdr.lpData, hdr.dwBytesRecorded))

            hdr.dwFlags         = 0
            hdr.dwBytesRecorded = 0
            winmm.waveInPrepareHeader(hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))
            winmm.waveInAddBuffer(hwi, ctypes.byref(hdr), ctypes.sizeof(hdr))

    time.sleep(0.01)
