# Voice-To-Text-Typer
Convert voice to text and type that text where your cursor is. **Works on Windows only**. No internet required. Doesn't send/store anything to the cloud, everything happens locally on device. The voice->text is leveraging OpenAI's whisper model (https://github.com/openai/whisper). It only records when you're holding **ctrl+win**. Feel free to change the specific model (it's using base.en by default).

The only 3rd party library is "whisper" and its dependencies. The rest of the code is using std Python libraries. Making this happen with ctypes was a headache but reduces the supply chain risk. The audio is saved in a file called "recording.wav" in the current working directory, everytime you talk that file is overwritten.

https://github.com/user-attachments/assets/b88d6287-5947-4669-ad33-3753913f35ad

### Requirements 
1. Windows (tested on Windows 11)
2. Python

### Installation
For troubleshooting follow https://github.com/openai/whisper guidance
```
python -m pip install whisper, torch, torchvision torchaudio
```

### Running the Code
```
python voice_to_text_typer.py
```
* Enter the ID of the audio device you want ("0" is the default)
* To record audio press (ctrl+win) and talk
* Release ctrl+win and observe that within a second or two the text will appear where your cursor is
