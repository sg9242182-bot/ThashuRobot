# Local Python environment and model setup

Keep the Python virtual environment and model weights outside the Git checkout. Pulling, switching branches, cleaning, or pushing `~/ThashuRobot` then cannot remove them or add them to a commit.

Use these persistent, user-owned locations on the Raspberry Pi:

- Virtual environment: `~/.venvs/thashu`
- Model weights: `~/.local/share/thashu/models/`

The code defaults to that model directory. Set `THASHU_MODELS_DIR` only if you deliberately choose another location.

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
| Face recognition | `face/w600k_r50.onnx` | InsightFace `buffalo_l.zip` |
| Wake word | `openwakeword/hey_jarvis_v0.1.onnx` | openWakeWord downloader |
| Wake word support | `openwakeword/melspectrogram.onnx`, `embedding_model.onnx` | Same openWakeWord download |
| Local LLM | `llm/qwen2.5-0.5b-instruct-q4_k_m.gguf` | Official Qwen GGUF repository |
| Piper voice | `piper/en_US-lessac-low.onnx` and matching `.onnx.json` | Piper voices repository |
| Speech recognition | `whisper/` | faster-whisper downloads Whisper tiny on first initialization |

The face detector uses OpenCV's installed Haar cascade; it has no separate MobileNet model files. Piper's executable is software, not a model weight. The code defaults to `~/piper/piper/piper`; set `THASHU_PIPER_BIN` if it is installed elsewhere.

## Download the models

Activate the virtual environment above before installing packages or running Python commands:

```bash
cd ~/ThashuRobot/thashu
source ~/.venvs/thashu/bin/activate
export THASHU_MODELS_DIR="$HOME/.local/share/thashu/models"
python -m pip install --upgrade pip
python -m pip install openwakeword huggingface_hub faster-whisper scipy
```

### Wake word

```bash
python -c 'import os; from openwakeword.utils import download_models; download_models(model_names=["hey_jarvis_v0.1"], target_directory=os.path.join(os.environ["THASHU_MODELS_DIR"], "openwakeword"))'
```

### Face recognition

The official InsightFace model archive publishes a SHA-256 checksum. This downloads it to `/tmp`, verifies it, and extracts only the recognition model:

```bash
wget -O /tmp/thashu-buffalo_l.zip https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_l.zip
echo '80ffe37d8a5940d59a7384c201a2a38d4741f2f3c51eef46ebb28218a7b0ca2f  /tmp/thashu-buffalo_l.zip' | sha256sum -c -
python - <<'PY'
import os
from pathlib import Path
from zipfile import ZipFile

target = Path(os.environ["THASHU_MODELS_DIR"]) / "face" / "w600k_r50.onnx"
with ZipFile("/tmp/thashu-buffalo_l.zip") as zf:
    matches = [name for name in zf.namelist() if Path(name).name == target.name]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {target.name}; found {matches}")
    target.write_bytes(zf.read(matches[0]))
print(f"Installed {target} ({target.stat().st_size:,} bytes)")
PY
```

InsightFace labels its pretrained recognition models for non-commercial research use. Check that license before using this model commercially.

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

### Whisper tiny

The application downloads Whisper tiny into `$THASHU_MODELS_DIR/whisper/` when speech recognition initializes. To fetch it now:

```bash
python -c 'from voice.speech_to_text import _get_model; _get_model()'
```

### Verify

```bash
find "$THASHU_MODELS_DIR" -type f -printf '%p %s bytes\n' | sort
test -s "$THASHU_MODELS_DIR/face/w600k_r50.onnx"
test -s "$THASHU_MODELS_DIR/openwakeword/hey_jarvis_v0.1.onnx"
test -s "$THASHU_MODELS_DIR/openwakeword/melspectrogram.onnx"
test -s "$THASHU_MODELS_DIR/openwakeword/embedding_model.onnx"
test -s "$THASHU_MODELS_DIR/llm/qwen2.5-0.5b-instruct-q4_k_m.gguf"
test -s "$THASHU_MODELS_DIR/piper/en_US-lessac-low.onnx"
test -s "$THASHU_MODELS_DIR/piper/en_US-lessac-low.onnx.json"
git -C ~/ThashuRobot check-ignore -v thashu/models/face/w600k_r50.onnx
```

`git check-ignore` should report `thashu/models`; the active assets are in your home data directory, outside Git altogether.

## References

- [openWakeWord model downloader](https://github.com/dscripka/openWakeWord)
- [InsightFace model-zoo release and checksum](https://github.com/deepinsight/insightface/releases/tag/model-zoo)
- [InsightFace model licensing](https://github.com/deepinsight/insightface/blob/master/model_zoo/README.md)
- [Official Qwen 2.5 0.5B Instruct GGUF files](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/tree/main)
- [Piper en_US-lessac-low voice files](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/low)
- [faster-whisper `download_root` option](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py)
