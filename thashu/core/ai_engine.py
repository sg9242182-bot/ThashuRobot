from llama_cpp import Llama
import os
import re

from core.model_paths import model_path

# ── Load once at import time ──────────────────────────────────────────────────
_MODEL_PATH = model_path("llm", "qwen2.5-0.5b-instruct-q4_k_m.gguf")

_llm = Llama(
    model_path=_MODEL_PATH,
    n_ctx=512,          # small context = less RAM
    n_threads=4,        # use all Pi 4 cores
    n_gpu_layers=0,     # CPU only
    verbose=False
)

print("[AI ENGINE] Qwen2.5-0.5B loaded")

# ── Prompts ───────────────────────────────────────────────────────────────────
_SYSTEM_NORMAL = (
    "You are Thashu, a helpful robot assistant. "
    "Answer the user's actual question directly in one short sentence. "
    "If the input is unclear, incomplete, or nonsensical, reply exactly: "
    "I didn't understand that. Please say it again. "
    "Do not guess unclear words or add a preamble, unrelated facts, lists, or filler."
)

_SYSTEM_DEEP = (
    "You are Thashu, a helpful robot assistant. "
    "Answer the user's actual question directly in at most two short sentences. "
    "If the input is unclear, incomplete, or nonsensical, reply exactly: "
    "I didn't understand that. Please say it again. "
    "Do not guess unclear words or add a preamble, unrelated facts, lists, or filler."
)

# ── Main function (same signature as before) ──────────────────────────────────
def generate_response(prompt: str, mode: str = "normal") -> str:
    try:
        system = _SYSTEM_DEEP if mode == "deep" else _SYSTEM_NORMAL

        output = _llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt}
            ],
            max_tokens=56 if mode == "deep" else 32,
            temperature=0.2,
            stop=["User:", "Assistant:", "\n\n"]
        )

        text = output["choices"][0]["message"]["content"].strip()

        # Remove common role labels and enforce the requested short answer.
        for tag in ["Assistant:", "Answer:", "Thashu:"]:
            if text.startswith(tag):
                text = text[len(tag):].strip()

        text = " ".join(text.split())
        sentence_limit = 2 if mode == "deep" else 1
        sentences = re.split(r"(?<=[.!?])\\s+", text)
        text = " ".join(sentence.strip() for sentence in sentences[:sentence_limit]).strip()
        if text and text[-1] not in ".!?":
            text += "."
        if not text:
            text = "I didn't understand that. Please say it again."

        return text.strip()

    except Exception as e:
        print(f"[AI ERROR]: {e}")
        return "I am having trouble thinking right now."