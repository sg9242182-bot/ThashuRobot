class EmotionEngine:
    def __init__(self):
        self.current_mood = "neutral"

    def update_mood(self, user_input: str):
        text = user_input.lower()

        if any(word in text for word in ["angry", "hate", "bad"]):
            self.current_mood = "serious"

        elif any(word in text for word in ["happy", "great", "awesome"]):
            self.current_mood = "friendly"

        else:
            self.current_mood = "neutral"

    def get_mood(self):
        return self.current_mood