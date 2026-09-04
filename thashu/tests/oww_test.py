import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly
from openwakeword.model import Model

model = Model(
    wakeword_models=["models/wake_word/hey_jarvis_v0.1.onnx"],
    inference_framework="onnx",
)

DEVICE = 2          # your USB Audio Device
RATE = 48000
BLOCK = 5460

def callback(indata, frames, time, status):
    audio48 = indata[:, 0].astype(np.int16)

    audio16 = np.ascontiguousarray(
        resample_poly(audio48, up=1, down=3).astype(np.int16)
    )

    result = model.predict(audio16)
    print(result)

with sd.InputStream(
    device=DEVICE,
    samplerate=RATE,
    channels=1,
    dtype="int16",
    blocksize=BLOCK,
    callback=callback,
):
    print("Say: Hey Jarvis")
    while True:
        pass