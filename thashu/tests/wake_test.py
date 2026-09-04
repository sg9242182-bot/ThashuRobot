import pyaudio
import numpy as np
from openwakeword.utils import AudioFeatures
from scipy.signal import resample as scipy_resample
import onnxruntime as ort
import time

preprocessor = AudioFeatures(inference_framework='onnx')
session = ort.InferenceSession('/home/tharun/thashu/models/wake_word/hey_thashu.onnx')

pa = pyaudio.PyAudio()
stream = pa.open(rate=48000, channels=1, format=pyaudio.paInt16,
                 input=True, frames_per_buffer=5460)

print("🤖 Warming up...")
buffer = np.zeros(24000, dtype=np.int16)
COOLDOWN = 2.0
last_detected = 0
high_score_count = 0
NOISE_GATE = 4000

# Fill buffer with real audio before starting detection
# 24000 samples / 1820 per chunk = ~14 chunks needed
warmup_chunks = 14
for _ in range(warmup_chunks):
    chunk = np.frombuffer(stream.read(5460, exception_on_overflow=False), dtype=np.int16)
    chunk_resampled = scipy_resample(chunk, 1820).astype(np.int16)
    buffer = np.roll(buffer, -1820)
    buffer[-1820:] = chunk_resampled

print("🤖 Listening for 'Hey Thashu'...")

while True:
    chunk = np.frombuffer(stream.read(5460, exception_on_overflow=False), dtype=np.int16)
    chunk_resampled = scipy_resample(chunk, 1820).astype(np.int16)
    buffer = np.roll(buffer, -1820)
    buffer[-1820:] = chunk_resampled

    rms = np.sqrt(np.mean(buffer.astype(np.float32)**2))
    if rms < NOISE_GATE:
        high_score_count = 0
        continue

    feat = preprocessor.embed_clips(buffer[np.newaxis, :])[0].flatten().astype(np.float32)
    score = session.run(None, {'input': feat[np.newaxis, :]})[0][0]

    if score > 0.85:
        high_score_count += 1
    else:
        high_score_count = 0

    now = time.time()
    if high_score_count >= 3 and (now - last_detected) > COOLDOWN:
        last_detected = now
        high_score_count = 0
        print(f"✅ Hey Thashu detected! (score: {score:.2f})")
        # 👉 your robot action here