from typing import Optional
import threading
from PySide6.QtMultimedia import QAudioOutput, QAudioFormat
from PySide6.QtCore import QObject, QByteArray, QIODevice
import time

class VirtualMicOutput:
    def __init__(self, device_info=None):
        self.device_info = device_info
        self._audio_output: Optional[QAudioOutput] = None
        self._running = False
        self._volume = 0.85
        self._device_id = getattr(device_info, "id", None) if device_info is not None else None
        self._reconnect_interval = 3.0
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_stop = threading.Event()
        self._status_callback = None

    def Start(self, sample_rate: int = 48000, channels: int = 2, sample_format=None) -> None:
        # skeleton: create QAudioOutput configured to device if possible
        try:
            fmt = QAudioFormat()
            fmt.setSampleRate(sample_rate)
            fmt.setChannelCount(channels)
            # leave other format fields default for now
            if self.device_info is not None:
                try:
                    try:
                        self._audio_output = QAudioOutput(self.device_info.device, fmt)
                    except Exception:
                        self._audio_output = QAudioOutput(self.device_info.device)
                except Exception:
                    self._audio_output = QAudioOutput()
            else:
                self._audio_output = QAudioOutput()
            try:
                self._audio_output.setVolume(self._volume)
            except Exception:
                pass
            # record target format
            try:
                self.target_sample_rate = sample_rate
                self.target_channels = channels
                self.target_width = 2  # 16-bit
            except Exception:
                self.target_sample_rate = sample_rate
                self.target_channels = channels
                self.target_width = 2
            # prepare internal QIODevice buffer for feeding audio
            try:
                class BufferIO(QIODevice):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                        self.buffer = bytearray()
                        self.open(QIODevice.ReadOnly)

                    def readData(self, maxlen: int) -> bytes:
                        # return up to maxlen bytes, pad with silence if empty
                        if not self.buffer:
                            return b"\x00" * maxlen
                        n = min(len(self.buffer), maxlen)
                        out = bytes(self.buffer[:n])
                        del self.buffer[:n]
                        if n < maxlen:
                            out += b"\x00" * (maxlen - n)
                        return out

                    def bytesAvailable(self) -> int:
                        return len(self.buffer)

                self._io = BufferIO()
                self._io_lock = threading.Lock()
                try:
                    self._audio_output.start(self._io)
                except Exception:
                    # some QAudioOutput variants may require start without IO first
                    try:
                        self._audio_output.start()
                    except Exception:
                        pass
                # connect stateChanged to attempt recovery
                try:
                    self._audio_output.stateChanged.connect(self._on_state_changed)
                except Exception:
                    pass
            except Exception:
                pass
            self._running = True
        except Exception:
            self._audio_output = None
            self._running = False

    def WriteFrames(self, pcm_bytes: bytes) -> None:
        # skeleton: no-op for now; real implementation will feed a QIODevice
        if not self._running:
            return
        try:
            # append to io buffer
            if hasattr(self, "_io") and self._io is not None:
                with self._io_lock:
                    # append and cap buffer size to ~1s to avoid unbounded growth
                    max_buf = 48000 * 2 * 2  # sample_rate * channels * bytes_per_sample
                    self._io.buffer += pcm_bytes
                    if len(self._io.buffer) > max_buf:
                        excess = len(self._io.buffer) - max_buf
                        del self._io.buffer[:excess]
                    # notify status OK when we have data queued
                    try:
                        if self._status_callback is not None:
                            self._status_callback("播放中")
                    except Exception:
                        pass
        except Exception:
            pass
        # future: the QAudioOutput pulls from _io.readData

    def Stop(self) -> None:
        try:
            if self._audio_output is not None:
                try:
                    try:
                        self._audio_output.stop()
                    except Exception:
                        pass
                except Exception:
                    pass
            self._running = False
        finally:
            self._audio_output = None
            try:
                if hasattr(self, "_io") and self._io is not None:
                    try:
                        self._io.close()
                    except Exception:
                        pass
                    self._io = None
            except Exception:
                pass
            # stop reconnect thread if any
            try:
                self._reconnect_stop.set()
            except Exception:
                pass

    @property
    def DeviceId(self) -> Optional[str]:
        return self._device_id

    def setVolume(self, volume: float) -> None:
        self._volume = volume
        try:
            if self._audio_output is not None:
                self._audio_output.setVolume(volume)
        except Exception:
            pass

    def set_status_callback(self, cb):
        """Set a callback `cb(text: str)` to receive status updates."""
        self._status_callback = cb

    def _reconnect_loop(self):
        """Background loop that periodically attempts to find the saved device and recreate the QAudioOutput."""
        try:
            from audio.device_manager import DeviceManager
        except Exception:
            DeviceManager = None

        while not self._reconnect_stop.is_set():
            try:
                # attempt to resolve saved device
                new_dev = None
                if DeviceManager is not None and self.device_info is not None:
                    saved_id = getattr(self.device_info, "id", None)
                    saved_desc = getattr(self.device_info, "description", None)
                    try:
                        new_dev = DeviceManager.find_output_by_id_or_description(saved_id, saved_desc)
                    except Exception:
                        new_dev = None

                # recreate audio output if found
                try:
                    fmt = QAudioFormat()
                    fmt.setSampleRate(getattr(self, "target_sample_rate", 48000))
                    fmt.setChannelCount(getattr(self, "target_channels", 2))
                    if new_dev is not None:
                        try:
                            self._audio_output = QAudioOutput(new_dev, fmt)
                        except Exception:
                            self._audio_output = QAudioOutput(new_dev)
                    else:
                        if self.device_info is not None and hasattr(self.device_info, "device"):
                            try:
                                self._audio_output = QAudioOutput(self.device_info.device, fmt)
                            except Exception:
                                self._audio_output = QAudioOutput(self.device_info.device)
                        else:
                            # nothing resolved yet
                            self._audio_output = None
                except Exception:
                    self._audio_output = None

                if self._audio_output is not None:
                    try:
                        self._audio_output.setVolume(self._volume)
                    except Exception:
                        pass
                    try:
                        if hasattr(self, "_io") and self._io is not None:
                            try:
                                self._audio_output.start(self._io)
                            except Exception:
                                try:
                                    self._audio_output.start()
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    try:
                        # reconnect succeeded
                        if self._status_callback is not None:
                            desc = None
                            try:
                                desc = new_dev.description() if new_dev is not None else getattr(self.device_info, "description", None)
                            except Exception:
                                desc = None
                            if desc:
                                self._status_callback(f"已恢复: {desc}")
                            else:
                                self._status_callback("已恢复")
                    except Exception:
                        pass
                    # stop loop
                    try:
                        self._reconnect_stop.set()
                    except Exception:
                        pass
                    break

                # notify retry status and wait
                try:
                    if self._status_callback is not None:
                        self._status_callback("重试中...")
                except Exception:
                    pass
            except Exception:
                pass
            # sleep before next attempt
            time.sleep(self._reconnect_interval)
        # cleanup
        try:
            self._reconnect_thread = None
        except Exception:
            pass

    def _on_state_changed(self, state) -> None:
        # simple recovery: if audio output becomes Stopped/Idle unexpectedly while running, try to restart
        try:
            from PySide6.QtMultimedia import QAudio
            if not self._running:
                return
            # QAudio.ActiveState / IdleState / StoppedState / SuspendedState
            try:
                if state == QAudio.StoppedState or state == QAudio.IdleState:
                    # call status callback
                    try:
                        if self._status_callback is not None:
                            self._status_callback("设备失效，尝试恢复...")
                    except Exception:
                        pass
                    # stop current audio output
                    try:
                        if self._audio_output is not None:
                            try:
                                self._audio_output.stop()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # start a reconnect thread if not already running
                    try:
                        if self._reconnect_thread is None or not self._reconnect_thread.is_alive():
                            self._reconnect_stop.clear()
                            self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
                            self._reconnect_thread.start()
                    except Exception:
                        pass
                    except Exception:
                        pass
        except Exception:
            pass


class MonitorOutput(VirtualMicOutput):
    """MonitorOutput uses the same skeleton but represents local listening."""
    pass
