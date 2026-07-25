#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "virtual_mic.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {
            "enabled": False,
            "mode": "microphone_only",
            "notes": [
                "This mode only routes MicroSound audio into a selected microphone-like input path.",
                "It does not capture your own voice.",
            ],
        }
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    print("Virtual mic helper is ready.")
    print(f"Configuration path: {CONFIG_PATH}")
    print()
    print("Next steps:")
    print("1. Install a system-level virtual audio device if your OS supports it.")
    print("2. In your voice app, select this device as the microphone input.")
    print("3. Play audio through MicroSound and confirm only the audio stream is routed.")
