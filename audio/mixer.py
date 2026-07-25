import threading
import time
from typing import List

from .file_source import FileAudioSource

# Internal format: 16-bit signed little-endian, stereo, 48000 Hz
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2  # bytes per sample


def _mix_bytes(buffers: List[bytes]) -> bytes:
    # simple mixing: sum 16-bit samples with clipping
    if not buffers:
        return b""
    max_len = max(len(b) for b in buffers)
    # pad buffers
    bufs = [b.ljust(max_len, b"\x00") for b in buffers]
    import array
    out = array.array('h', [0] * (max_len // 2))
    for b in bufs:
        arr = array.array('h')
        arr.frombytes(b)
        for i in range(len(arr)):
            out[i] = max(min(out[i] + arr[i], 32767), -32768)
    return out.tobytes()


class AudioMixer:
    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self.sources: List[FileAudioSource] = []
        self.lock = threading.Lock()

    def AddSource(self, source: FileAudioSource) -> None:
        with self.lock:
            self.sources.append(source)

    def RemoveSource(self, source: FileAudioSource) -> None:
        with self.lock:
            try:
                self.sources.remove(source)
            except ValueError:
                pass

    def Mix(self, num_frames: int) -> bytes:
        with self.lock:
            buffers = []
            for src in list(self.sources):
                data = src.ReadFrames(num_frames)
                if not data:
                    # remove source at EOS
                    try:
                        self.sources.remove(src)
                    except ValueError:
                        pass
                    continue
                buffers.append(data)
        mixed = _mix_bytes(buffers)
        return mixed


class AudioEngine:
    def __init__(self, mixer: AudioMixer, outputs: List[object], frame_size: int = 1024):
        self.mixer = mixer
        self.outputs = outputs
        self.frame_size = frame_size
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self):
        frame_rate = self.mixer.sample_rate
        frames = self.frame_size
        frame_duration = frames / frame_rate
        while self._running:
            pcm = self.mixer.Mix(frames)
            if pcm:
                # write same immutable pcm to all outputs, converting if target format differs
                for out in list(self.outputs):
                    try:
                        tgt_bs = getattr(out, "target_sample_rate", None)
                        tgt_ch = getattr(out, "target_channels", None)
                        tgt_w = getattr(out, "target_width", None)
                        if tgt_bs and (tgt_bs != self.mixer.sample_rate or tgt_ch != self.mixer.channels or tgt_w != 2):
                            try:
                                from .format_converter import convert_raw_pcm
                                pcm2 = convert_raw_pcm(pcm, self.mixer.sample_rate, self.mixer.channels, 2, tgt_bs, tgt_ch, tgt_w)
                            except Exception:
                                pcm2 = pcm
                        else:
                            pcm2 = pcm
                        out.WriteFrames(pcm2)
                    except Exception:
                        pass
            time.sleep(frame_duration)
*** End Patch