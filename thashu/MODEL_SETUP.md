# Local model setup

Thashu's model weights are machine-local files. Keep them under `thashu/models/`; the repository's `.gitignore` excludes `models/` at every depth, so these files will not be committed.

The code resolves paths from the installed source files, not the shell's current directory. On the Raspberry Pi, the expected directory is:

```text
/home/tharun/ThashuRobot/thashu/models/
```

## Required assets

| Feature | Local path | How it is obtained |
|---|---|---|
| Face recognition | `models/face/w600k_r50.onnx` | Extracted from InsightFace `buffalo_l.zip` |
| Wake word | `models/openwakeword/hey_jarvis_v0.1.onnx` | openWakeWord downloader |
| Wake word support | `models/openwakeword/melspectrogram.onnx`, `embedding_model.onnx` | Same openWakeWord download |
| Local LLM | `models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf` | Official Qwen GGUF repository |
| Piper voice | `models/piper/en_US-lessac-low.onnx` and matching `.onnx.json` | Piper voices repository |
| Speech recognition | `models/whisper/` | faster-whisper downloads Whisper tiny on first initialization |

The face detector uses OpenCV's installed Haar cascade; there are no separate MobileNet SSD files to download. Piper's executable is software, not a model weight. The code defaults to `~/piper/piper/piper`; set `THASHU_PIPER_BIN` if it is installed elsewhere.

## Download on the Pi

Run these commands in the project's existing Python virtual environment:

```bash
cd ~/ThashuRobot/thashu
mkdir -p models/{face,openwakeword,llm,piper,whisper}
df -h .
```

The Qwen model is about 1.12 GB; make sure the filesystem has enough free space before downloading.

### Wake word

```bash
python3 -c 'from openwakeword.utils import download_models; download_models(model_names=["hey_jarvis_v0.1"], target_directory="models/openwakeword")'
```

### Face recognition

The official InsightFace model archive publishes a SHA-256 checksum. This downloads it to `/tmp`, verifies it, and extracts only the recognition model into the ignored project-local directory:

```bash
wget -O /tmp/thashu-buffalo_l.zip https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_l.zip
echo '80ffe37d8a5940d59a7384c201a2a38d4741f2f3c51eef46ebb28218a7b0ca2f  /tmp/thashu-buffalo_l.zip' | sha256sum -c -
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile

archive = Path("/tmp/thashu-buffalo_l.zip")
target = Path("models/face/w600k_r50.onnx")
with ZipFile(archive) as zf:
    matches = [name for name in zf.namelist() if Path(name).name == target.name]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one {target.name} in archive; found {matches}")
    target.write_bytes(zf.read(matches[0]))
print(f"Installed {target} ({target.stat().st_size:,} bytes)")
PY
```

InsightFace labels its pretrained recognition models for non-commercial research use. Check that license before using this model commercially.

### Qwen local LLM

```bash
python3 -m pip install -U huggingface_hub
hf download Qwen/Qwen2.5-1.5B-Instruct-GGUF qwen2.5-1.5b-instruct-q4_k_m.gguf --local-dir models/llm
```

If the `hf` command is not on the virtual environment's PATH after installation, reopen the shell in the same environment and run the command again.

### Piper voice

```bash
curl -fL 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/low/en_US-lessac-low.onnx' -o models/piper/en_US-lessac-low.onnx
curl -fL 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/low/en_US-lessac-low.onnx.json' -o models/piper/en_US-lessac-low.onnx.json
```

### Whisper tiny

The application downloads Whisper tiny into `models/whisper/` the first time speech recognition initializes. To fetch it before running the robot:

```bash
python3 -c 'from voice.speech_to_text import _get_model; _get_model()'
```

### Check the files

```bash
find models -type f -printf '%p %s bytes\\n' | sort
test -s models/face/w600k_r50.onnx
test -s models/openwakeword/hey_jarvis_v0.1.onnx
test -s models/openwakeword/melspectrogram.onnx
test -s models/openwakeword/embedding_model.onnx
test -s models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf
test -s models/piper/en_US-lessac-low.onnx
test -s models/piper/en_US-lessac-low.onnx.json
git check-ignore models
```

The last command should print `models`, confirming the local weights are ignored by Git.

## References

- [openWakeWord model downloader](https://github.com/dscripka/openWakeWord)
- [InsightFace model-zoo release and checksum](https://github.com/deepinsight/insightface/releases/tag/model-zoo)
- [InsightFace model licensing](https://github.com/deepinsight/insightface/blob/master/model_zoo/README.md)
- [Official Qwen 2.5 1.5B Instruct GGUF files](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/main)
- [Piper en_US-lessac-low voice files](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/low)
- [faster-whisper `download_root` option](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py)
