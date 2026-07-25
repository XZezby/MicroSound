from typing import Optional
from pydub import AudioSegment

class FileAudioSource:
    def __init__(self, path: str, target_sample_rate: int = 48000, target_channels: int = 2):
        self.path = path
        self.target_sample_rate = target_sample_rate
        self.target_channels = target_channels
        self.segment: Optional[AudioSegment] = None
        self.position_ms = 0
        self._load()
        self._stopped = False

    def _load(self):
        try:
            self.segment = AudioSegment.from_file(self.path)
            # convert to target
            if self.segment.frame_rate != self.target_sample_rate:
                self.segment = self.segment.set_frame_rate(self.target_sample_rate)
            if self.segment.channels != self.target_channels:
                self.segment = self.segment.set_channels(self.target_channels)
            # ensure sample width 2 (16-bit)
            if self.segment.sample_width != 2:
                self.segment = self.segment.set_sample_width(2)
        except Exception:
            self.segment = None

    def ReadFrames(self, num_frames: int) -> bytes:
        if self.segment is None or self._stopped:
            return b""
        # num_frames -> ms based on sample_rate
        ms_per_frame = 1000.0 / self.target_sample_rate
        ms = int(num_frames * ms_per_frame)
        start = int(self.position_ms)
        end = start + ms
        if start >= len(self.segment):
            return b""
        chunk = self.segment[start:end]
        self.position_ms = end
        return chunk.raw_data

    def Seek(self, position: int) -> None:
        # position in frames
        self.position_ms = int(position / self.target_sample_rate * 1000)

    def Stop(self) -> None:
        self._stopped = True
        self.segment = None
*** End Patch