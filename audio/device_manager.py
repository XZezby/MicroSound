import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PySide6.QtMultimedia import QMediaDevices, QAudioDevice

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config" / "device_selection.json"


@dataclass
class DeviceInfo:
    id: str
    description: str
    device: QAudioDevice


class DeviceManager:
    @staticmethod
    def _qdevice_id(qdevice: QAudioDevice) -> str:
        try:
            # QAudioDevice.id() returns QByteArray; decode to str when possible
            raw = qdevice.id()
            try:
                return bytes(raw).decode("utf-8")
            except Exception:
                try:
                    return str(raw)
                except Exception:
                    return qdevice.description()
        except Exception:
            return qdevice.description()

    @staticmethod
    def get_output_devices() -> List[DeviceInfo]:
        devices: List[DeviceInfo] = []
        for d in QMediaDevices.audioOutputs():
            devices.append(DeviceInfo(id=DeviceManager._qdevice_id(d), description=d.description(), device=d))
        return devices

    @staticmethod
    def get_input_devices() -> List[DeviceInfo]:
        devices: List[DeviceInfo] = []
        for d in QMediaDevices.audioInputs():
            devices.append(DeviceInfo(id=DeviceManager._qdevice_id(d), description=d.description(), device=d))
        return devices

    @staticmethod
    def save_selected_endpoint(role: str, endpoint_id: Optional[str]) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if CONFIG_PATH.exists():
            try:
                with CONFIG_PATH.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                data = {}
        data[role] = endpoint_id
        with CONFIG_PATH.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    @staticmethod
    def load_selected_endpoint(role: str) -> Optional[str]:
        if not CONFIG_PATH.exists():
            return None
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data.get(role)
        except Exception:
            return None

    @staticmethod
    def find_output_by_id_or_description(endpoint_id: Optional[str], description: Optional[str]):
        try:
            for d in QMediaDevices.audioOutputs():
                try:
                    raw = d.id()
                    try:
                        did = bytes(raw).decode("utf-8")
                    except Exception:
                        did = str(raw)
                    if endpoint_id and did == endpoint_id:
                        return d
                    if description and d.description() == description:
                        return d
                except Exception:
                    pass
        except Exception:
            pass
        return None
