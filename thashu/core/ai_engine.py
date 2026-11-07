from llama_cpp import Llama
import os
import re
import time

from core.model_paths import model_path

# ── Load once at import time ──────────────────────────────────────────────────
_MODEL_PATH = model_path("llm", "qwen2.5-0.5b-instruct-q4_k_m.gguf")

try:
    _requested_threads = int(os.environ.get("THASHU_LLM_THREADS", "4"))
except ValueError:
    _requested_threads = 4
_LLM_THREADS = max(1, min(os.cpu_count() or 4, _requested_threads))

_llm = Llama(
    model_path=_MODEL_PATH,
    n_ctx=512,          # small context = less RAM
    n_threads=_LLM_THREADS,
    n_gpu_layers=0,     # CPU only
    verbose=False
)

print("[AI ENGINE] Qwen2.5-0.5B loaded")
print(f"[AI ENGINE] CPU threads: {_LLM_THREADS}")

# ── Prompts ───────────────────────────────────────────────────────────────────
_SYSTEM_NORMAL = (
    "You are Thashu, a helpful robot assistant. "
    "Answer the user's actual question in one direct, complete sentence, usually no more than 18 words. "
    "If the input is unclear, incomplete, or nonsensical, reply exactly: "
    "I didn't understand that. Please say it again. "
    "Do not guess unclear words or add a preamble, unrelated facts, lists, or filler."
)

_SYSTEM_DEEP = (
    "You are Thashu, a helpful robot assistant. "
    "Answer the user's actual question in one concise, complete sentence, usually no more than 18 words. "
    "If the input is unclear, incomplete, or nonsensical, reply exactly: "
    "I didn't understand that. Please say it again. "
    "Do not guess unclear words or add a preamble, unrelated facts, lists, or filler."
)

def warmup_model() -> bool:
    """Run one discarded token so first real inference avoids cold backend setup."""
    started = time.monotonic()
    try:
        _llm.create_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_NORMAL},
                {"role": "user", "content": "Say ready."},
            ],
            max_tokens=1,
            temperature=0.0,
            stop=["User:", "Assistant:", "\n\n"],
        )
        print(f"[AI ENGINE] Startup warm-up = {time.monotonic() - started:.2f}s")
        return True
    except Exception as exc:
        print(f"[AI ENGINE] Startup warm-up failed: {exc}")
        return False


# ── Main function (same signature as before) ──────────────────────────────────
def generate_response(prompt: str, mode: str = "normal") -> str:
    try:
        system = _SYSTEM_DEEP if mode == "deep" else _SYSTEM_NORMAL

        output = _llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt}
            ],
            max_tokens=32,
            temperature=0.2,
            stop=["User:", "Assistant:", "\n\n"]
        )

        text = output["choices"][0]["message"]["content"].strip()

        # Remove common role labels and keep the first complete sentence.
        for tag in ["Assistant:", "Answer:", "Thashu:"]:
            if text.startswith(tag):
                text = text[len(tag):].strip()

        text = " ".join(text.split())
        sentences = re.split(r"(?<=[.!?])\s+", text)
        text = sentences[0].strip() if sentences else ""
        if text and text[-1] not in ".!?":
            text += "."
        if not text:
            text = "I didn't understand that. Please say it again."

        return text.strip()

    except Exception as e:
        print(f"[AI ERROR]: {e}")
        return "I am having trouble thinking right now."