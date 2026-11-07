# Local Python environment and model setup

Keep the Python virtual environment and model weights outside the Git checkout. Pulling, switching branches, cleaning, or pushing `~/ThashuRobot` then cannot remove them or add them to a commit.

Use these persistent, user-owned locations on the Raspberry Pi:

- Virtual environment: `~/.venvs/thashu`
- Model weights: `~/.local/share/thashu/models/`

The code defaults to that model directory. Set `THASHU_MODELS_DIR` only if you deliberately choose another location. `THASHU_DATA_DIR` can similarly override the local data directory.

## Create the virtual environment

A virtual environment is local to this Pi and is not downloaded by Git:

```bash
deactivate 2>/dev/null || true
unset VIRTUAL_ENV
hash -r
mkdir -p ~/.venvs
python3 -m venv ~/.venvs/thashu
source ~/.venvs/thashu/bin/activate
python -c 'import sys; print(sys.executable)'
python -m pip --version
```

Both reported paths should be inside `/home/tharun/.venvs/thashu`. If `python3 -m venv` reports that `ensurepip` is unavailable, install the OS package with `sudo apt install python3-venv` and retry. In a new terminal, activate it with:

```bash
source ~/.venvs/thashu/bin/activate
```

## Set up the model directory

Run from the repository's Python project directory:

```bash
cd ~/ThashuRobot/thashu
export THASHU_MODELS_DIR="$HOME/.local/share/thashu/models"
mkdir -p "$THASHU_MODELS_DIR"/{face,openwakeword,llm,piper,whisper}
df -h "$HOME"
```

If you already downloaded files into the old checkout-local `models/` directory, copy them into the persistent location. This leaves the originals in place until you have verified the application:

```bash
if [ -d "$HOME/ThashuRobot/thashu/models" ]; then
  cp -an "$HOME/ThashuRobot/thashu/models/." "$THASHU_MODELS_DIR/"
fi
find "$THASHU_MODELS_DIR" -type f -printf '%p %s bytes\n' | sort
```

## Required model assets

| Feature | Path under `$THASHU_MODELS_DIR` | Source |
|---|---|---|
| Person / upper-body tracking | `pose_landmarker_lite.task` | MediaPipe Pose Landmarker Lite |
| Face detection (optional acceleration) | `face/face_detection_yunet_2023mar.onnx` | OpenCV Zoo YuNet (MIT); Haar fallback is supported |
| Wake word | `openwakeword/hey_jarvis_v0.1.onnx` | openWakeWord downloader |
| Wake word support | `openwakeword/melspectrogram.onnx`, `embedding_model.onnx` | Same openWakeWord download |
| Local LLM | `llm/qwen2.5-0.5b-instruct-q4_k_m.gguf` | Official Qwen GGUF repository |
| Piper voice | `piper/en_US-lessac-low.onnx` and matching `.onnx.json` | Piper voices repository |
| Speech recognition | `whisper/` | faster-whisper downloads Whisper tiny on first initialization |

The face detector uses machine-local YuNet when installed and falls back to OpenCV's Haar cascade. Dlib estimates landmarks within detected crops. Confirmed dlib descriptors are stored under `~/.local/share/thashu/data/people_faces_dlib.json`, outside the checkout; the enrollment flow stores no face photos. Legacy ArcFace data at `people_faces.json` is not read or modified. Piper's executable is software, not a model weight. The code defaults to `~/piper/piper/piper`; set `THASHU_PIPER_BIN` if it is installed elsewhere.

## Download the models

Activate the virtual environment above before installing packages or running Python commands:

```bash
cd ~/ThashuRobot/thashu
source ~/.venvs/thashu/bin/activate
export THASHU_MODELS_DIR="$HOME/.local/share/thashu/models"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install openwakeword huggingface_hub faster-whisper scipy
```

### Pose Lite person tracking

The detector uses MediaPipe Pose Landmarker Lite through the tested Raspberry Pi-compatible MediaPipe 0.10.15 runtime. Keep the task model in the persistent model directory:

```bash
curl -fL 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task' -o "$THASHU_MODELS_DIR/pose_landmarker_lite.task"
test -s "$THASHU_MODELS_DIR/pose_landmarker_lite.task"
```

### Wake word

```bash
python -c 'import os; from openwakeword.utils import download_models; download_models(model_names=["hey_jarvis_v0.1"], target_directory=os.path.join(os.environ["THASHU_MODELS_DIR"], "openwakeword"))'
```

### Face recognition

The active recognizer is dlib. Install it through the project's normal requirements:

```bash
cd ~/ThashuRobot/thashu
source ~/.venvs/thashu/bin/activate
python -m pip install -r requirements.txt
```

Dlib's five-point predictor and 128-D recognition model are supplied by `face_recognition_models`; no ArcFace recognition model download is needed. YuNet is an optional face-box detector acceleration. If it is absent, the existing Haar detector still supplies face crops to dlib.

Dlib descriptors are not compatible with legacy ArcFace embeddings. The dlib database is `~/.local/share/thashu/data/people_faces_dlib.json`. Existing `people_faces.json` and `w600k_r50.onnx` files are left untouched; enroll identities again through the confirmed enrollment flow before expecting recognition.

### Optional YuNet face detector

Dlib estimates five facial landmarks inside each detected face crop. YuNet accelerates face-box detection when installed; the existing Haar fallback can also provide boxes to dlib.

OpenCV 4.10's contrib build provides FaceDetectorYN. Download the small OpenCV Zoo model into the machine-local model directory:

```bash
curl -fL 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx' -o "$THASHU_MODELS_DIR/face/face_detection_yunet_2023mar.onnx"
test -s "$THASHU_MODELS_DIR/face/face_detection_yunet_2023mar.onnx"
```

The OpenCV Zoo YuNet model is MIT-licensed: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet

### Qwen local LLM

The chosen Qwen2.5-0.5B-Instruct Q4_K_M file is about 491 MB. It is a better fit for fast, short voice-assistant replies on the Pi than the previous 1.5B suggestion; it is less capable at complex reasoning. The code expects this exact filename. [Official Qwen GGUF files](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/tree/main).


```bash
hf download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_k_m.gguf --local-dir "$THASHU_MODELS_DIR/llm"
```

### Piper voice

```bash
curl -fL 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/low/en_US-lessac-low.onnx' -o "$THASHU_MODELS_DIR/piper/en_US-lessac-low.onnx"
curl -fL 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/low/en_US-lessac-low.onnx.json' -o "$THASHU_MODELS_DIR/piper/en_US-lessac-low.onnx.json"
```

### Whisper tiny.en

The application downloads Whisper tiny.en into `$THASHU_MODELS_DIR/whisper/` when speech recognition initializes. To fetch it now:

```bash
python -c 'from voice.speech_to_text import _get_model; _get_model()'
```

### Verify

```bash
find "$THASHU_MODELS_DIR" -type f -printf '%p %s bytes\n' | sort
test -s "$THASHU_MODELS_DIR/pose_landmarker_lite.task"
test -s "$THASHU_MODELS_DIR/openwakeword/hey_jarvis_v0.1.onnx"
test -s "$THASHU_MODELS_DIR/openwakeword/melspectrogram.onnx"
test -s "$THASHU_MODELS_DIR/openwakeword/embedding_model.onnx"
test -s "$THASHU_MODELS_DIR/llm/qwen2.5-0.5b-instruct-q4_k_m.gguf"
test -s "$THASHU_MODELS_DIR/piper/en_US-lessac-low.onnx"
test -s "$THASHU_MODELS_DIR/piper/en_US-lessac-low.onnx.json"
git -C ~/ThashuRobot check-ignore -v thashu/models/face/face_detection_yunet_2023mar.onnx
```

`git check-ignore` should report `thashu/models`; the active assets are in your home data directory, outside Git altogether.

## References

- [MediaPipe Pose Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker)
- [openWakeWord model downloader](https://github.com/dscripka/openWakeWord)
- [Official Qwen 2.5 0.5B Instruct GGUF files](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/tree/main)
- [Piper en_US-lessac-low voice files](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/low)
- [faster-whisper `download_root` option](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py)


## Low-latency streaming Piper setup (Phase 11)

The application prefers the in-process `libpiper` backend. It keeps the voice model resident and streams decoder chunks to ALSA. This requires split ONNX files and the native library. Until both are available, Thashu uses the existing Piper CLI fallback.

Run once on the Raspberry Pi. Keep MediaPipe's required protobuf version; do not install the PyPI `piper-tts` package for the splitter.

```bash
cd ~/ThashuRobot
git clone --depth 1 https://github.com/OHF-Voice/piper1-gpl.git ~/piper1-gpl
cd ~/ThashuRobot/thashu
source ~/.venvs/thashu/bin/activate

python -m pip install --force-reinstall "onnx==1.17.0" "protobuf==4.25.5" "numpy==1.26.4"
python -m pip check
```

If `pip check` reports a MediaPipe/protobuf conflict, stop and share the output. Split the existing voice using the splitter from the cloned upstream source:

```bash
MODEL="$HOME/.local/share/thashu/models/piper/en_US-lessac-low.onnx"
PYTHONPATH="$HOME/piper1-gpl/src" python -m piper.split_voice_for_streaming "$MODEL"
ls -lh "$MODEL.encoder.onnx" "$MODEL.decoder.onnx"
```

Install the native build tools. CMake must be version 3.26 or newer:

```bash
sudo apt update
sudo apt install -y build-essential cmake git
cmake --version
```

Then build and install libpiper:

```bash
cmake -S "$HOME/piper1-gpl/libpiper" \
  -B "$HOME/piper1-gpl/libpiper/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$HOME/piper1-gpl/libpiper/install"
cmake --build "$HOME/piper1-gpl/libpiper/build" --parallel 2
cmake --install "$HOME/piper1-gpl/libpiper/build"

ls -lh "$HOME/piper1-gpl/libpiper/install/lib/libpiper.so"
ls -d "$HOME/piper1-gpl/libpiper/install/share/espeak-ng-data"
```

The runtime checks those default paths. For a different install location, set `THASHU_LIBPIPER` and `THASHU_ESPEAK_DATA_DIR` when launching Thashu. Upstream references: [voice splitting and streaming](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/STREAMING.md), [libpiper build instructions](https://github.com/OHF-Voice/piper1-gpl/blob/main/libpiper/README.md).

