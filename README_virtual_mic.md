# Virtual microphone mode

This project can be used in a way that only routes MicroSound playback audio into a microphone-like input path.

## Requirements
- A system-level virtual audio device or loopback-capable setup.
- A voice app that allows selecting a microphone input.

## Workflow
1. Run the helper script:
   - python virtual_mic.py
2. In your voice app, choose the virtual microphone device as the microphone input.
3. Play audio through MicroSound.

This mode is intended to avoid capturing your own voice and only carry the playback audio stream.
