#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "virtual_mic_settings.json"


def _build_template() -> dict:
    return {
        "virtual_mic": {
            "required_driver": "VB-Audio Virtual Cable, VoiceMeeter, or similar",
            "notes": [
                "真正的系统级虚拟麦克风需要安装虚拟音频驱动。",
                "如果你已经安装了 VB-Audio / VoiceMeeter，可以把它设置为语音软件的输入设备。",
                "然后再把本项目的音频输出切到对应的输出设备。",
            ],
        },
        "devices": {
            "inputs": [],
            "outputs": [],
        },
    }


def _try_list_devices() -> tuple[list[dict], list[dict]]:
    try:
        import sounddevice  # type: ignore
    except Exception:
        return [], []

    try:
        devices = sounddevice.query_devices()
    except Exception:
        return [], []

    inputs: list[dict] = []
    outputs: list[dict] = []

    for index, device in enumerate(devices):
        name = str(device.get("name", ""))
        if not name:
            continue
        if device.get("max_input_channels", 0) > 0:
            inputs.append({"index": index, "name": name})
        if device.get("max_output_channels", 0) > 0:
            outputs.append({"index": index, "name": name})

    return inputs, outputs


def main() -> int:
    template = _build_template()
    inputs, outputs = _try_list_devices()
    template["devices"]["inputs"] = inputs
    template["devices"]["outputs"] = outputs

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(template, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("Virtual mic setup configuration written to:")
    print(CONFIG_PATH)
    print()
    print("What to do next:")
    print("1. Install a virtual audio driver such as VB-Audio Virtual Cable or VoiceMeeter.")
    print("2. In your voice app, set the virtual mic as the microphone input.")
    print("3. In this project, choose the corresponding audio output device if available.")
    print()
    print("Detected input devices:")
    if inputs:
        for item in inputs:
            print(f" - {item['index']}: {item['name']}")
    else:
        print(" - none detected")

    print()
    print("Detected output devices:")
    if outputs:
        for item in outputs:
            print(f" - {item['index']}: {item['name']}")
    else:
        print(" - none detected")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
