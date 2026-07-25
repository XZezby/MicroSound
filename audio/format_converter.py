from pydub import AudioSegment
import io

# Basic format conversion utilities.
# Strategy: use pydub AudioSegment for sample rate / channel / sample width conversion.
# Input: raw PCM bytes, source sample_rate, channels, sample_width (bytes)
# Output: raw PCM bytes in target format.


def convert_raw_pcm(pcm_bytes: bytes, src_rate: int, src_channels: int, src_width: int, tgt_rate: int, tgt_channels: int, tgt_width: int) -> bytes:
    if not pcm_bytes:
        return b""
    try:
        seg = AudioSegment.from_raw(
            io.BytesIO(pcm_bytes),
            sample_width=src_width,
            frame_rate=src_rate,
            channels=src_channels,
        )
        if seg.frame_rate != tgt_rate:
            seg = seg.set_frame_rate(tgt_rate)
        if seg.channels != tgt_channels:
            seg = seg.set_channels(tgt_channels)
        if seg.sample_width != tgt_width:
            seg = seg.set_sample_width(tgt_width)
        return seg.raw_data
    except Exception:
        # fallback: return original bytes
        return pcm_bytes
*** End Patch