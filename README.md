# Voice-To-Text-Typer
Convert voice to text and type that text where your cursor is. **Works on Windows only**. No internet required. Doesn't send/store anything to the cloud, everything happens locally on device. The voice->text is leveraging OpenAI's whisper model (https://github.com/openai/whisper). It only records when you're holding **ctrl+win**. Feel free to change the specific model it's using (base.en by default).

The only 3rd party library is "whisper" and its dependencies. The rest of the code is using std Python libraries. Making this happen with ctypes was a headache but reduces the supply chain risk.

### Requirements 
1. Windows (tested on Windows 11)
2. Python
3. OpenAI Whisper
