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
        # Exact id/description match first, then fuzzy description substring match (case-insensitive)
        try:
            outputs = list(QMediaDevices.audioOutputs())
            # exact id match
            if endpoint_id:
                for d in outputs:
                    try:
                        raw = d.id()
                        try:
                            did = bytes(raw).decode("utf-8")
                        except Exception:
                            did = str(raw)
                        if did == endpoint_id:
                            return d
                    except Exception:
                        pass
            # exact description match
            if description:
                for d in outputs:
                    try:
                        if d.description() == description:
                            return d
                    except Exception:
                        pass
            # fuzzy substring (case-insensitive)
            if description:
                desc_low = description.lower()
                for d in outputs:
                    try:
                        if desc_low in d.description().lower():
                            return d
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    @staticmethod
    def get_reconnect_interval(default: float = 3.0) -> float:
        """Read reconnect interval (seconds) from the saved config if present, else return default."""
        try:
            if CONFIG_PATH.exists():
                with CONFIG_PATH.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                val = data.get("reconnect_interval")
                if val is None:
                    return default
                try:
                    return float(val)
                except Exception:
                    return default
        except Exception:
            pass
        return default
