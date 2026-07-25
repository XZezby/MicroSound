from typing import Optional
import threading
from PySide6.QtMultimedia import QAudioOutput, QAudioFormat
from PySide6.QtCore import QObject, QByteArray, QIODevice

class VirtualMicOutput:
    def __init__(self, device_info=None):
        self.device_info = device_info
        self._audio_output: Optional[QAudioOutput] = None
        self._running = False
        self._volume = 0.85
        self._device_id = getattr(device_info, "id", None) if device_info is not None else None

    def Start(self, sample_rate: int = 48000, channels: int = 2, sample_format=None) -> None:
        # skeleton: create QAudioOutput configured to device if possible
        try:
            fmt = QAudioFormat()
            fmt.setSampleRate(sample_rate)
            fmt.setChannelCount(channels)
            # leave other format fields default for now
            if self.device_info is not None:
                try:
                    self._audio_output = QAudioOutput(self.device_info.device)
                except Exception:
                    self._audio_output = QAudioOutput()
            else:
                self._audio_output = QAudioOutput()
            try:
                self._audio_output.setVolume(self._volume)
            except Exception:
                pass
            # prepare internal QIODevice buffer for feeding audio
            try:
                class BufferIO(QIODevice):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                        self.buffer = bytearray()
                        self.open(QIODevice.ReadOnly)

                    def readData(self, maxlen: int) -> bytes:
                        if not self.buffer:
                            return bytes(maxlen)
                        n = min(len(self.buffer), maxlen)
                        out = bytes(self.buffer[:n])
                        del self.buffer[:n]
                        if n < maxlen:
                            out += b"\x00" * (maxlen - n)
                        return out

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
                    self._io.buffer += pcm_bytes
        except Exception:
            pass
        # future: write to internal QIODevice feeding QAudioOutput
        # For now, store last buffer for inspection (no playback)
        try:
            self._last_buffer = pcm_bytes
        except Exception:
            pass

    def Stop(self) -> None:
        try:
            if self._audio_output is not None:
                try:
                    self._audio_output.stop()
                except Exception:
                    pass
            self._running = False
        finally:
            self._audio_output = None

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


class MonitorOutput(VirtualMicOutput):
    """MonitorOutput uses the same skeleton but represents local listening."""
    pass
