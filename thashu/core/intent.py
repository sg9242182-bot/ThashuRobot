class IntentEngine:
    def __init__(self):
        self.intents = {
            "greeting": {
                "phrases": ["hello", "hi", "hey", "hiya", "yo", "sup", "howdy", "greetings"],
                "weight": 2
            },
            "casual": {
                "phrases": [
                    "how are you", "how are you doing", "how do you do",
                    "how you doing", "you good", "you okay", "are you okay",
                    "are you alright", "how is it going", "how's it going",
                    "how goes it", "everything okay", "whats up", "what's up",
                    "you doing alright", "are you all right"
                ],
                "weight": 5
            },
            "identity": {
                "phrases": [
                    "who are you", "your name", "what is your name",
                    "what's your name", "whats your name", "ur name",
                    "whats ur name", "what ur name", "tell me your name",
                    "what do they call you", "what should i call you",
                    "do you have a name", "what are you called",
                    "who made you", "who created you", "who built you",
                    "who programmed you", "who is your creator", "who owns you"
                ],
                "weight": 4
            },
            "time": {
                "phrases": [
                    "what is the time", "whats the time", "what's the time",
                    "what time is it", "current time", "tell me the time"
                ],
                "weight": 5
            },
            "positive_emotion": {
                "words": ["happy", "good", "great", "awesome", "nice", "cool", "perfect", "wonderful"],
                "weight": 1
            },
            "negative_emotion": {
                "words": ["sad", "bad", "tired", "angry", "upset", "frustrated", "bored"],
                "weight": 1
            },
            "command": {
                "words": ["stop", "start", "move", "turn", "pause", "resume", "wait", "go", "reset", "quiet"],
                "weight": 4
            },
            "deep_question": {
                "phrases": [
                    "what is", "how does", "why is", "explain",
                    "define", "difference between", "what does",
                    "meaning of", "how do", "why does", "what are",
                    "how to", "what happens", "who invented", "when was",
                    "tell me about", "how can", "what causes"
                ],
                "weight": 3
            },
            "question": {
                "words": ["what", "how", "why", "when", "where", "which", "who"],
                "weight": 1
            }
        }

    def detect(self, text: str) -> dict:
        text = text.lower().strip()
        clean_text = ''.join(c for c in text if c.isalnum() or c.isspace()).strip()
        words = clean_text.split()

        scores = {}

        # ===== EXACT MATCH PRIORITY =====
        for intent, data in self.intents.items():
            if "phrases" in data:
                for phrase in data["phrases"]:
                    if phrase == clean_text:
                        return {
                            "intent": intent,
                            "confidence": 1.0,
                            "all_scores": {intent: 10}
                        }

        # ===== SCORING =====
        for intent, data in self.intents.items():
            score = 0

            if "phrases" in data:
                for phrase in data["phrases"]:
                    if phrase in clean_text:
                        score += data["weight"]

            if "words" in data:
                for word in words:
                    if word in data["words"]:
                        score += data["weight"]

            if score > 0:
                scores[intent] = score

        if not scores:
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "all_scores": {}
            }

        # ===== CASUAL OVERRIDE =====
        if "casual" in scores and scores["casual"] >= 5:
            return {
                "intent": "casual",
                "confidence": 1.0,
                "all_scores": scores
            }

        # ===== DEEP QUESTION OVERRIDE =====
        # deep_question beats generic question always
        if "deep_question" in scores and "question" in scores:
            del scores["question"]

        # ===== BEST INTENT =====
        best_intent = max(scores, key=scores.get)
        max_score   = scores[best_intent]
        confidence  = min(max_score / 5, 1.0)

        return {
            "intent": best_intent,
            "confidence": round(confidence, 2),
            "all_scores": scores
        }