from llama_cpp import Llama
import os

# ── Load once at import time ──────────────────────────────────────────────────
_MODEL_PATH = os.path.expanduser("~/thashu/models/llm/qwen2.5-1.5b-q4_k_m.gguf")

_llm = Llama(
    model_path=_MODEL_PATH,
    n_ctx=512,          # small context = less RAM
    n_threads=4,        # use all Pi 4 cores
    n_gpu_layers=0,     # CPU only
    verbose=False
)

print("[AI ENGINE] Qwen2.5-1.5B loaded")

# ── Prompts ───────────────────────────────────────────────────────────────────
_SYSTEM_NORMAL = (
    "You are Thashu, a robot assistant. "
    "Give a short, direct, factual answer in 2-3 sentences max. "
    "No lists. No stories. No filler words."
)

_SYSTEM_DEEP = (
    "You are Thashu, a precise AI assistant. "
    "Explain clearly and simply in 3-4 sentences max. "
    "Stay on topic. No lists. No stories."
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
            max_tokens=40,
            temperature=0.3,
            stop=["User:", "Assistant:", "\n\n"]
        )

        text = output["choices"][0]["message"]["content"].strip()

        # ── Clean ─────────────────────────────────────────────────────────────
        for tag in ["Assistant:", "Answer:", "Thashu:"]:
            if text.startswith(tag):
                text = text[len(tag):].strip()

        text = text.replace("\n", " ").strip()

        # Keep max 2 sentences
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if len(sentences) >= 2:
            text = sentences[0] + ". " + sentences[1] + "."
        elif len(sentences) == 1:
            text = sentences[0] + "."
        else:
            text = "I did not understand that."

        return text.strip()

    except Exception as e:
        print(f"[AI ERROR]: {e}")
        return "I am having trouble thinking right now."