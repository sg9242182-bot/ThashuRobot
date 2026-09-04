from core.decision import decide
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from emotions.emotion_engine import EmotionEngine
from core.ai_engine import generate_response
from core.response_manager import ResponseManager
from personality.personality_engine import PersonalityEngine
from core.quick_responses import QuickResponses
from core.intent import IntentEngine

import re


class Brain:
    def __init__(self):
        print("[BRAIN] Initialized")

        self.long_memory = LongTermMemory()
        self.memory = ShortTermMemory()
        self.emotion = EmotionEngine()
        self.response_manager = ResponseManager()
        self.personality = PersonalityEngine()
        self.quick = QuickResponses()
        self.intent_engine = IntentEngine()

    def process(self, user_input: str):

        if not user_input:
            return ""

        print(f"[BRAIN] Processing: {user_input}")

        text = user_input.lower().strip()

        # ===== STEP 0: QUICK RESPONSES (before everything) =====
        # Must run before intent detection.
        # Intent engine classifies many quick-response phrases as deep_question
        # (e.g. "what are you doing" → deep_question → Qwen, 20-34s).
        # 48 entries in quick_responses are currently unreachable because intent
        # gates them to deep_question or unknown before this check is reached.
        # quick.get_response() handles its own deep-question filtering: direct/
        # partial key matches return immediately; only unmatched inputs with deep
        # patterns return None, falling through to the full pipeline below.
        quick_reply = self.quick.get_response(user_input)
        if quick_reply:
            self.memory.add(user_input, quick_reply)
            print("[FAST RESPONSE]")
            return quick_reply

        # ===== STEP 1: BLOCK WEAK INPUT =====
        if len(text.split()) < 2:
            return "Say that clearly."

        # ===== STEP 2: INTENT =====
        intent_data = self.intent_engine.detect(user_input)
        intent = intent_data["intent"]
        confidence = intent_data["confidence"]

        print("[INTENT]", intent, "| Confidence:", confidence)

        # ===== TIME =====
        if intent == "time":
            from datetime import datetime
            return f"The time is {datetime.now().strftime('%H:%M')}"

        # ===== STEP 3: PERSONALITY =====
        self.personality.update(user_input)

        # ===== STEP 4: LONG MEMORY =====
        if "my name is" in text:
            name = user_input.split("is")[-1].strip()
            self.long_memory.set("user_name", name)

            response = f"Okay, I will remember your name is {name}."
            self.memory.add(user_input, response)
            return response

        if "what is my name" in text:
            name = self.long_memory.get("user_name")

            if name:
                response = f"Your name is {name}."
            else:
                response = "I don't know your name yet."

            self.memory.add(user_input, response)
            return response

        # ===== STEP 5: MATH HANDLER =====
        nums = re.findall(r'\d+\.?\d*', text)

        if any(op in text for op in ["plus", "minus", "add", "subtract", "into", "times", "multiply", "x", "by", "divide"]) and len(nums) >= 2:
            try:
                nums = list(map(float, nums))

                # ADD
                if "plus" in text or "add" in text:
                    return str(sum(nums))

                # SUBTRACT
                if "minus" in text or "subtract" in text:
                    result = nums[0]
                    for n in nums[1:]:
                        result -= n
                    return str(result)

                # MULTIPLY
                if any(op in text for op in ["into", "times", "multiply", "x"]):
                    result = 1
                    for n in nums:
                        result *= n
                    return str(result)

                # DIVIDE
                if "by" in text or "divide" in text:
                    result = nums[0]
                    for n in nums[1:]:
                        if n != 0:
                            result /= n
                    return str(result)

            except:
                pass

        # ===== STEP 6: BASIC KNOWLEDGE FIX =====
        if "atmosphere" in text and "atmospheric" not in text:
            return "The atmosphere is the layer of gases surrounding the Earth."

        if "refraction" in text and "atmospheric" not in text:
            return "Refraction is the bending of light when it passes through different mediums."

        # ===== STEP 7: EMOTION =====
        self.emotion.update_mood(user_input)
        mood = self.emotion.get_mood()

        # ===== STEP 8: CONTEXT =====
        context = self.memory.get_context()

        # ===== STEP 9: DECISION =====
        decision_result = decide(user_input, context)

        # ===== STEP 10: ROUTING =====
        if intent == "deep_question" and confidence >= 0.75:
            decision_result = "DEEP_MODE"

        if intent == "casual" and decision_result == "AI_FALLBACK":
            return "Say that clearly."

        # ===== STEP 11: AI =====
        if decision_result in ["AI_FALLBACK", "DEEP_MODE"]:

            mode = "deep" if decision_result == "DEEP_MODE" else "normal"

            prompt = f"""
You are Thashu.

Answer in 1-2 clear sentences.

Do NOT:
- say "I do not have the ability"
- mention AI limitations
- say "Sure" or "I'd be happy"
- generate lists
- go off topic

User: {user_input}

Answer:
"""

            ai_response = generate_response(prompt=prompt, mode=mode)

            # ===== SAFETY =====
            if not ai_response or len(ai_response.strip()) == 0:
                ai_response = "I didn’t understand that."

            # ===== CLEAN AI OUTPUT =====
            ai_response = ai_response.strip()

            bad_phrases = [
                "sure", "of course", "here are", "here's",
                "i'd be happy", "as an ai", "thashu:",
                "answer:", "question:", "assistant:"
            ]

            for phrase in bad_phrases:
                if ai_response.lower().startswith(phrase):
                    ai_response = ai_response[len(phrase):].strip()

            if "1." in ai_response:
                ai_response = ai_response.split("1.")[-1].strip()

            ai_response = ai_response.split("\n")[0].strip()
            ai_response = ai_response.lstrip("!:- ")

            if len(ai_response.split()) < 3:
                ai_response = "I didn’t understand that."

            print("[RAW AI RESPONSE]", ai_response)

        else:
            ai_response = decision_result

        # ===== STEP 12: FILTER =====
        filtered_response = self.response_manager.handle(user_input, ai_response)

        # ===== STEP 13: PERSONALITY =====
        final_response = self.personality.apply(filtered_response, mood)

        # ===== STEP 14: MEMORY =====
        if final_response:
            self.memory.add(user_input, final_response)

        print("[PERSONALITY]", self.personality.get_personality())
        print("[MEMORY]", self.memory.get_context())

        return final_response