"""Server-side noise suppression for bike/fan/hum/whistle sounds.

Browser noiseSuppression is weak against loud environmental noise, so we clean
the clip with spectral gating (noisereduce) before it reaches Whisper.
Stationary sounds (fan hum, engine drone, whistles) are removed using the
first half-second as the noise profile; speech passes through.
"""
import tempfile
import numpy as np
from app.core.logging import get_logger

log = get_logger("stt.denoise")
TARGET_SR = 16000


def _decode_mono_16k(path: str) -> np.ndarray:
    import av
    container = av.open(path)
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="s16", layout="mono", rate=TARGET_SR)
    chunks: list[bytes] = []
    for frame in container.decode(stream):
        for rf in resampler.resample(frame):
            chunks.append(bytes(rf.planes[0]))
    if not chunks:
        raise RuntimeError("Could not decode audio")
    pcm = np.frombuffer(b"".join(chunks), dtype=np.int16).astype(np.float32) / 32768.0
    return pcm


def denoise_to_wav(src_path: str) -> str:
    """Returns path to a cleaned 16kHz mono WAV. Falls back to src on any error."""
    try:
        import noisereduce as nr
        from scipy.io import wavfile
    except ImportError:
        log.warning("noisereduce/scipy missing — skipping denoise (pip install noisereduce)")
        return src_path
    try:
        y = _decode_mono_16k(src_path)
        if len(y) < TARGET_SR // 2:
            return src_path  # too short to profile noise, leave it
        # Quiet room? Skip the ~2s denoise pass entirely — nothing to remove.
        floor = float(np.sqrt(np.mean(y[: TARGET_SR // 2] ** 2)))
        if floor < 0.015:
            return src_path
        # First 0.5s = assumed background (user starts speaking after mic opens)
        noise = y[: TARGET_SR // 2]
        clean = nr.reduce_noise(y=y, sr=TARGET_SR, y_noise=noise,
                                stationary=True, prop_decrease=0.75)
        out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wavfile.write(out.name, TARGET_SR, (np.clip(clean, -1, 1) * 32767).astype(np.int16))
        return out.name
    except Exception as e:
        log.warning(f"denoise failed, using raw audio: {e}")
        return src_path
