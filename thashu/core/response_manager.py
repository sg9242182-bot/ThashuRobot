class ResponseManager:
    def __init__(self):
        print("[RESPONSE] Manager initialized")

    def is_garbage(self, user_input: str, ai_response: str) -> bool:

        if not ai_response:
            return True

        response = ai_response.strip()
        response_lower = response.lower()
        user_lower = user_input.lower()

        # ===== 1. EMPTY / TOO SHORT =====
        if len(response_lower) < 2:
            return True

        # ===== 2. PROMPT / INSTRUCTION LEAK =====
        if any(x in response_lower for x in [
            "you are thashu",
            "instructions:",
            "rules:",
            "assistant:",
            "user:",
            "question:",
            "answer:",
            "context:"
        ]):
            return True

        # ===== 3. AI TEMPLATE GARBAGE =====
        if response_lower.startswith(("sure,", "here are")):
            return True

        if any(x in response_lower for x in [
            "here are some",
            "based on your question",
            "according to your request"
        ]):
            return True

        # ===== 4. GENERIC BAD RESPONSES =====
        if any(x in response_lower for x in [
            "i don't know",
            "as an ai",
            "i am not sure",
            "cannot understand",
            "undefined"
        ]):
            return True

        # ===== 5. ALLOW DEFINITIONS (MOVE UP HERE) =====
        if any(x in response_lower for x in [
            " is a ",
            " is the ",
            " refers to ",
            " means "
        ]):
            return False

        # ===== 6. REPETITION DETECTION =====
        words = response_lower.split()
        if len(words) > 5:
            if len(set(words)) < len(words) * 0.5:
                return True

        # ===== 7. MEANINGLESS SHORT =====
        if response_lower in ["ok", "okay", "yes", "no"]:
            return True

        # ===== 8. BROKEN LIST =====
        if response_lower.endswith(("1.", "2.", "3.", "a.", "b.")):
            return True

        # ===== 9. QUESTION INSTEAD OF ANSWER =====
        if response_lower.startswith(("can you", "what do you", "would you")):
            return True

        # ===== 10. LIGHT RELEVANCE CHECK =====
        user_words = set(user_lower.split())
        response_words = set(response_lower.split())

        ignore = {
            "the", "is", "a", "an", "what", "how", "why",
            "are", "you", "i", "to", "of", "and", "it"
        }

        user_words -= ignore
        response_words -= ignore

        if len(user_words) >= 2:
            overlap = user_words.intersection(response_words)

            # only reject if response is very weak
            if len(overlap) == 0 and len(response_words) < 4:
                return True

        return False

    def handle(self, user_input: str, ai_response: str) -> str:

        if not user_input or user_input.strip() == "":
            return None

        if self.is_garbage(user_input, ai_response):
            return "I didn’t understand that. Say it again."

        response = ai_response.strip()

        # ===== CLEAN =====
        response = " ".join(response.split())

        # ===== FIX ENDING =====
        if not response.endswith((".", "!", "?")):
            response += "."

        return response