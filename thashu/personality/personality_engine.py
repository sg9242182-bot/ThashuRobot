class PersonalityEngine:
    def __init__(self):
        print("[PERSONALITY] Advanced system initialized")

        self.current_personality = "neutral"

        # Behavior tracking
        self.history = []
        self.max_history = 10

    # =============================
    # UPDATE BASED ON USER INPUT
    # =============================
    def update(self, user_input: str):

        text = user_input.lower()

        self.history.append(text)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        self._analyze_behavior()

    # =============================
    # ANALYZE USER PATTERN
    # =============================
    def _analyze_behavior(self):

        funny_score = 0
        soft_score = 0
        serious_score = 0

        for text in self.history:

            if any(w in text for w in ["joke", "fun", "laugh", "roast"]):
                funny_score += 1

            if any(w in text for w in ["hi", "hello", "nice", "thanks"]):
                soft_score += 1

            if any(w in text for w in ["calculate", "what is", "explain", "solve"]):
                serious_score += 1

        # ===== DECISION =====
        if funny_score > max(soft_score, serious_score):
            self.current_personality = "funny"

        elif soft_score > max(funny_score, serious_score):
            self.current_personality = "cute"

        elif serious_score > max(funny_score, soft_score):
            self.current_personality = "serious"

        else:
            self.current_personality = "neutral"

    # =============================
    # APPLY PERSONALITY TO RESPONSE
    # =============================
    def apply(self, response: str, mood: str) -> str:

        if not response:
            return response

        response = response.strip()

        # ===== REMOVE AI-TYPE TALK =====
        banned = [
            "as an ai",
            "i am an ai",
            "i cannot",
            "i do not have access",
        ]

        for b in banned:
            if b in response.lower():
                return "I am not sure. Say it again."

        # ===== CLEAN RESPONSE =====
        response = self._clean_text(response)

        # ===== APPLY PERSONALITY STYLE =====
        if self.current_personality == "funny":
            response = self._funny_style(response)

        elif self.current_personality == "cute":
            response = self._cute_style(response)

        elif self.current_personality == "serious":
            response = self._serious_style(response)

        else:
            response = self._neutral_style(response)

        # ===== MOOD OVERRIDE =====
        if mood == "serious":
            response = self._serious_style(response)

        return response

    # =============================
    # TEXT CLEANING
    # =============================
    def _clean_text(self, text: str) -> str:

        # Remove extra spaces
        text = " ".join(text.split())

        # Fix double punctuation
        text = text.replace("..", ".").replace("!!", "!")

        return text

    # =============================
    # PERSONALITY STYLES
    # =============================

    def _neutral_style(self, text: str) -> str:
        return text

    def _serious_style(self, text: str) -> str:
        return text  # direct, no changes

    def _funny_style(self, text: str) -> str:

        # Light humor injection (not stupid)
        if len(text.split()) > 5:
            return text + " That was simple."
        else:
            return text + " Easy."

    def _cute_style(self, text: str) -> str:

        # Soft tone (no emojis)
        if not text.endswith("."):
            text += "."
        return text + " Okay."

    # =============================
    # DEBUG
    # =============================
    def get_personality(self):
        return self.current_personality