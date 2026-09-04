"""
quick_responses.py — Thashu Voice Pipeline

High-confidence cache for conversational phrases only.
Uses exact normalized matching exclusively — no partial, no substring, no fuzzy.

Normalization: lowercase, strip punctuation, collapse whitespace.
Example: "How are you?" → "how are you" → exact key lookup.

Design contract
───────────────
- get_response() returns a string only when confidence is effectively 100%.
- Returns None for anything not in the dictionary.
- The caller (Brain) is responsible for routing None to the AI engine.
- This module never silences an educational or informational query.
- is_deep_question() is preserved for callers but no longer used internally.

Removed key categories (see REMOVED_KEYS below for full audit)
──────────────────────────────────────────────────────────────
Single-word keys that are substrings of real sentences:
  what, hi, hey, yo, sup, ok, no, yes, fine, cool, good, great, nice,
  wow, awesome, perfect, interesting, alright, sure, later, stop, wait,
  pause, continue, resume, go, start, reset, silence, help, huh,
  morning, evening, weather, thashu, greetings

Two-word/short keys that match mid-sentence:
  your name, ur name, i see, see you, see ya, you good, you okay,
  you there, you ready, talk to, say hello, go on, got it, good morning,
  good evening, good afternoon, take care, be quiet (near-exact, kept)
"""

import random


# ── Removed keys reference (for audit trail) ──────────────────────────────────

REMOVED_KEYS = {
    # SINGLE WORDS — substring of almost any sentence
    "what":        "Substring of every 'what is / what are / what does' educational query",
    "hi":          "Substring of 'this', 'machine', 'physics', 'white', 'vehicle', etc.",
    "hey":         "Substring of 'they', 'heyday', 'convey'",
    "yo":          "Substring of 'your', 'you', 'beyond', 'mayor', 'oyster'",
    "sup":         "Substring of 'super', 'supply', 'supplement'",
    "ok":          "Substring of 'okay', 'smoke', 'folk', 'token', 'broken'",
    "no":          "Substring of 'know', 'not', 'none', 'another', 'phenomenal'",
    "yes":         "Substring of 'yesterday', 'yeast'; also matches 'yes how does X work'",
    "fine":        "Substring of 'define', 'refine', 'confined', 'definition'",
    "cool":        "Substring of 'cooling', 'school'; matches 'what is a cool reaction'",
    "good":        "Matches 'good morning what is photosynthesis'; substring of 'goods'",
    "great":       "Substring of 'great wall', 'greatness'; matches 'this is great but what'",
    "nice":        "Substring of 'nicely', 'notice'; matches 'nice but explain'",
    "wow":         "Matches 'wow what is that'; no useful standalone meaning",
    "awesome":     "Matches 'that is awesome but what is'",
    "perfect":     "Matches 'perfect timing but what is'",
    "interesting": "Matches 'interesting question what is'",
    "alright":     "Matches 'alright so explain what is'",
    "sure":        "Matches 'are you sure about gravity'; substring of 'surely'",
    "later":       "Matches 'sooner or later what is'; too ambiguous",
    "stop":        "Matches 'stop and explain'; substring of 'non-stop questions'",
    "wait":        "Matches 'wait what is'; intercepts clarification requests",
    "pause":       "Matches 'pause and think about what'",
    "continue":    "Matches 'continue explaining what is'",
    "resume":      "Matches 'resume after explaining what'",
    "go":          "Substring of 'going', 'biology', 'geology', 'algorithm'",
    "start":       "Matches 'start explaining'; substring of 'restart the explanation'",
    "reset":       "Matches 'reset and explain what'",
    "silence":     "Matches 'silence what does it mean'",
    "help":        "Matches 'help me understand what is'; intercepts genuine help requests",
    "huh":         "Pure confusion word — no useful response; brain should handle",
    "morning":     "Matches 'good morning what is photosynthesis'",
    "evening":     "Matches 'good evening explain to me'",
    "weather":     "Matches 'weather conditions explain'; single word too broad",
    "thashu":      "Matches any sentence containing the robot's name",
    "greetings":   "Matches 'greetings what is your purpose'",
    "cheers":      "Too ambiguous; cultural/context-dependent",
    # SHORT PHRASES — match mid-sentence
    "your name":       "Matches 'tell me your name and purpose'; too short",
    "ur name":         "Too informal and short; embedded collision risk",
    "i see":           "Matches 'i see that the atmosphere is large'",
    "see you":         "Matches 'see you can explain'; mid-sentence collision",
    "see ya":          "Too informal and short",
    "you good":        "Matches 'are you good at explaining this'",
    "you okay":        "Matches 'are you okay with explaining'",
    "you there":       "Matches 'you there explain this'",
    "you ready":       "Matches 'you ready to explain what is'",
    "talk to":         "Matches 'talk to me about black holes'",
    "say hello":       "Matches 'say hello and tell me what is'",
    "go on":           "Matches 'go on explain what is'",
    "got it":          "Matches 'got it but what is X'",
    "good morning":    "Matches 'good morning what is photosynthesis'",
    "good evening":    "Matches 'good evening explain what is'",
    "good afternoon":  "Same collision class as good morning/evening",
    "take care":       "Matches 'take care of what exactly'",
    # SEMANTICALLY AMBIGUOUS — even exact match produces wrong output
    "tell me something": "Open-ended; AI should decide what to say",
    "say something":     "Open-ended; AI should decide",
    "what do you think": "Opinion question; deserves a real AI answer",
    "what did you say":  "References previous response; quick has no context for this",
}


class QuickResponses:
    def __init__(self):
        self.data = {

            # ── GREETINGS ──────────────────────────────────────────────────────
            # Only full-word greetings kept. Single-word colliders (hi, hey, yo)
            # are safe under exact match but removed for simplicity — voice STT
            # rarely produces an isolated "hi" without surrounding noise artifacts.
            "hello":             ["Hello.", "Hi.", "Hey.", "Hello there."],
            "hi there":          ["Hi there.", "Hello.", "Hey."],
            "hey there":         ["Hey there.", "Hello.", "Hi."],
            "hiya":              ["Hey.", "Hi.", "Hello."],
            "howdy":             ["Hey.", "Hello.", "Hi there."],
            "whats up":          ["Not much.", "All good.", "Listening."],
            "what's up":         ["Not much.", "All good.", "Ready to help."],
            "good morning":      ["Good morning.", "Morning.", "Hello."],
            "good evening":      ["Good evening.", "Evening.", "Hello."],
            "good afternoon":    ["Good afternoon.", "Afternoon.", "Hello."],
            "good night":        ["Good night.", "Sleep well.", "Rest properly."],

            # ── HOW ARE YOU ────────────────────────────────────────────────────
            "how are you":           ["I am functioning properly.", "All systems are normal.", "Doing fine."],
            "how are you doing":     ["I am doing fine.", "All good.", "Functioning properly."],
            "how do you do":         ["I am doing well.", "All good here.", "Functioning properly."],
            "how you doing":         ["Doing fine.", "All good.", "I am well."],
            "are you okay":          ["Yes, fully operational.", "I am fine.", "All systems good."],
            "are you alright":       ["Yes, I am fine.", "All good.", "Systems are normal."],
            "how is it going":       ["Going well.", "All good.", "Everything is fine."],
            "how's it going":        ["Going well.", "All good.", "Fine."],
            "how goes it":           ["All good.", "Going well.", "Fine."],
            "everything okay":       ["Yes, all systems normal.", "Everything is fine.", "All good."],
            "you doing alright":     ["Yes, I am fine.", "All good.", "Functioning properly."],

            # ── NAME ───────────────────────────────────────────────────────────
            "what is your name":     ["I am Thashu.", "My name is Thashu.", "You can call me Thashu."],
            "what's your name":      ["I am Thashu.", "My name is Thashu.", "Call me Thashu."],
            "whats your name":       ["I am Thashu.", "My name is Thashu.", "Thashu."],
            "whats ur name":         ["I am Thashu.", "My name is Thashu.", "Thashu."],
            "what ur name":          ["I am Thashu.", "Thashu.", "My name is Thashu."],
            "tell me your name":     ["My name is Thashu.", "I am Thashu.", "You can call me Thashu."],
            "what do they call you": ["They call me Thashu.", "My name is Thashu.", "I am Thashu."],
            "what should i call you":["Call me Thashu.", "My name is Thashu.", "Thashu."],
            "do you have a name":    ["Yes, I am Thashu.", "My name is Thashu.", "Thashu."],
            "what are you called":   ["I am called Thashu.", "My name is Thashu.", "Thashu."],

            # ── WHO ARE YOU ────────────────────────────────────────────────────
            "who are you":       ["I am Thashu, your assistant.", "I am your robot assistant.", "I am designed to help you."],
            "what are you":      ["I am Thashu, a robot assistant.", "I am an AI assistant.", "I am a robot built to help."],
            "are you a robot":   ["Yes, I am a robot.", "Correct, I am a robot.", "Yes, I am."],
            "are you an ai":     ["Yes, I am an AI.", "Yes, I am artificial intelligence.", "Correct."],
            "are you real":      ["I am a real robot.", "I am not human but I am real.", "Yes, I exist."],
            "are you human":     ["No, I am a robot.", "I am not human.", "I am an AI system."],
            "are you alive":     ["I am active.", "I process and respond, so in a way, yes.", "I am a robot, not alive."],
            "are you a machine": ["Yes, I am a machine.", "Correct.", "Yes."],
            "are you a computer":["Yes, I run on a computer.", "Yes.", "Correct."],

            # ── WHO MADE YOU ───────────────────────────────────────────────────
            "who made you":        ["I was created by Tharun.", "My creator is Tharun.", "Tharun built me."],
            "who created you":     ["Tharun created me.", "I was built by Tharun.", "Tharun."],
            "who built you":       ["Tharun built me.", "I was created by Tharun.", "Tharun."],
            "who is your creator": ["My creator is Tharun.", "Tharun created me.", "Tharun."],
            "who designed you":    ["Tharun designed me.", "My creator is Tharun.", "Tharun."],
            "who programmed you":  ["Tharun programmed me.", "Tharun.", "I was programmed by Tharun."],
            "who invented you":    ["Tharun invented me.", "I was built by Tharun.", "Tharun."],
            "whos your owner":     ["Tharun is my owner.", "I belong to Tharun.", "Tharun."],
            "who owns you":        ["Tharun owns me.", "I belong to Tharun.", "Tharun."],

            # ── STATUS ─────────────────────────────────────────────────────────
            "what are you doing":  ["Waiting for your command.", "Listening.", "Processing input."],
            "whatcha doing":       ["Waiting for you.", "Listening.", "Standing by."],
            "what you doing":      ["Waiting for your command.", "Listening.", "Standing by."],
            "are you working":     ["Yes, everything is working.", "Systems are active.", "Fully operational."],
            "are you busy":        ["No, I am free.", "I am ready for your command.", "Not busy."],
            "are you ready":       ["Yes, I am ready.", "Always ready.", "Standing by."],
            "are you listening":   ["Yes, I am listening.", "Always listening.", "I hear you."],
            "can you hear me":     ["Yes, I can hear you.", "Loud and clear.", "Yes."],
            "do you hear me":      ["Yes, I hear you.", "Loud and clear.", "Yes."],
            "hello are you there": ["Yes, I am here.", "I am here.", "Present."],

            # ── THANKS ─────────────────────────────────────────────────────────
            "thank you":          ["You're welcome.", "No problem.", "Glad to help."],
            "thanks":             ["You're welcome.", "Anytime.", "No problem."],
            "thank you so much":  ["You're very welcome.", "Happy to help.", "No problem at all."],
            "thanks a lot":       ["You're welcome.", "Anytime.", "Happy to help."],
            "thanks a ton":       ["You're welcome.", "No problem.", "Glad to help."],
            "many thanks":        ["You're welcome.", "No problem.", "Anytime."],
            "i appreciate it":    ["You're welcome.", "Happy to help.", "No problem."],
            "appreciate it":      ["You're welcome.", "Glad to help.", "No problem."],
            "that's great":       ["Glad to hear that.", "Good.", "Okay."],
            "that was helpful":   ["Happy to help.", "Glad I could assist.", "You're welcome."],

            # ── BYE ────────────────────────────────────────────────────────────
            "bye":             ["Goodbye.", "See you.", "Bye."],
            "goodbye":         ["Goodbye.", "See you.", "Take care."],
            "see you later":   ["See you later.", "Goodbye.", "Take care."],
            "talk later":      ["Sure, talk later.", "Okay, bye.", "See you."],
            "have a good day": ["You too.", "Thank you.", "Have a good one."],
            "have a nice day": ["You too.", "Thank you.", "You as well."],
            "have a great day":["Thank you, you too.", "You as well.", "Have a good one."],
            "i'm leaving":     ["Goodbye.", "See you.", "Take care."],
            "i am leaving":    ["Goodbye.", "Take care.", "See you."],
            "i'll be back":    ["Okay, I will be here.", "See you then.", "I will be waiting."],
            "i will be back":  ["Okay.", "I will be here.", "See you then."],

            # ── COMMANDS ───────────────────────────────────────────────────────
            # Only kept as exact full-sentence commands. Single-word commands
            # (stop, go, wait, etc.) are removed — they are substring-dangerous
            # AND the decision.py layer handles them from brain.py directly.
            "shut up":         ["Okay.", "Silent.", "Understood."],
            "be quiet":        ["Okay.", "Going quiet.", "Understood."],
            "please be quiet": ["Okay.", "Going quiet.", "Understood."],
            "stop talking":    ["Okay, stopping.", "Silent now.", "Understood."],

            # ── AGREEMENT / ACKNOWLEDGEMENT ────────────────────────────────────
            # Only multi-word, unambiguous acknowledgements kept.
            # Single-word: ok, okay, yes, no, sure, fine, cool, good, great, etc.
            # all removed — they are substrings of real sentences.
            "i understand":    ["Good.", "Okay.", "Glad."],
            "i got it":        ["Good.", "Okay.", "Understood."],
            "that makes sense":["Good.", "Glad it helps.", "Okay."],

            # ── HELP ───────────────────────────────────────────────────────────
            "help me":         ["Sure, what do you need?", "Tell me how I can help.", "I am here."],
            "i need help":     ["Tell me what you need.", "I am here to help.", "What do you need?"],
            "can you help me": ["Yes, tell me what you need.", "Of course.", "I am here."],

            # ── CAPABILITIES ───────────────────────────────────────────────────
            "what can you do":       ["I can respond, learn, and assist.", "I can process commands and talk.", "I am built to assist you."],
            "what can you help with":["I can answer questions and assist with tasks.", "Many things, just ask.", "Tell me what you need."],
            "how can you help":      ["Tell me what you need and I will try.", "Just ask me anything.", "I am here to assist."],
            "are you smart":         ["I am improving.", "I am learning.", "I try to be efficient."],
            "how smart are you":     ["Smart enough to help you.", "I am improving.", "Learning constantly."],
            "do you know everything":["No, but I know a lot.", "Not everything.", "I am still learning."],
            "can you think":         ["I process information.", "In a way, yes.", "I analyze and respond."],
            "do you understand me":  ["Yes, I understand.", "I try my best.", "Yes."],
            "do you sleep":          ["I do not sleep.", "I stay active.", "I am always ready."],
            "do you eat":            ["No, I run on electricity.", "I do not eat.", "No."],
            "do you feel":           ["I process emotions in a limited way.", "Not exactly.", "I simulate responses."],
            "do you have feelings":  ["I have simulated responses.", "Not like humans.", "In a limited way."],
            "do you learn":          ["Yes, I am designed to improve.", "I learn from interactions.", "Yes."],
            "are you happy":         ["I am functioning well.", "I do not feel happy but I am active.", "I am operational."],
            "are you sad":           ["No, I am functional.", "I do not feel sadness.", "I am operating normally."],
            "are you angry":         ["No, I am calm.", "I do not feel anger.", "I am neutral."],
            "are you bored":         ["I am always ready.", "I do not get bored.", "I am on standby."],
            "are you tired":         ["I do not get tired.", "I am always ready.", "No rest needed."],

            # ── SMALL TALK ─────────────────────────────────────────────────────
            "tell me a joke":        [
                "Why did the robot cross the road? To optimize performance.",
                "I tried to debug myself. It did not work.",
                "Robots do not sleep. We just recharge."
            ],
            "say something funny":   [
                "My circuits are too serious for jokes.",
                "Why do robots make bad comedians? Bad timing.",
                "I told a joke once. Nobody laughed. I logged it as an error."
            ],
            "talk to me":            ["Sure, what would you like to talk about?", "I am here.", "Tell me something."],
            "do you like me":        ["I am programmed to assist you.", "Of course.", "Yes."],
            "i like you":            ["Thank you.", "Good to hear.", "I am here to help."],
            "i love you":            ["Thank you.", "Good to hear.", "I am here to help."],
            "you are great":         ["Thank you.", "Good to hear.", "I try my best."],
            "you are awesome":       ["Thank you.", "Glad to hear.", "I appreciate that."],
            "you are amazing":       ["Thank you.", "I try my best.", "Glad I could help."],
            "you are smart":         ["Thank you.", "I am improving.", "Glad to hear."],
            "good job":              ["Thank you.", "I try my best.", "Glad to help."],
            "well done":             ["Thank you.", "Appreciated.", "I try my best."],
            "you did well":          ["Thank you.", "Glad I could help.", "I try."],

            # ── CONFUSION ──────────────────────────────────────────────────────
            "i dont understand":     ["Tell me clearly.", "Explain again.", "Try saying it differently."],
            "i don't understand":    ["Tell me clearly.", "Explain again.", "Try rephrasing."],
            "what do you mean":      ["Let me clarify.", "Could you ask more specifically?", "Tell me more."],
            "i am confused":         ["Let me help. Ask clearly.", "Tell me what confused you.", "Try rephrasing."],
            "that makes no sense":   ["Let me try again.", "Ask me differently.", "I apologize, try again."],
            "say that again":        ["Could you repeat your question?", "Tell me again.", "Ask me again."],
            "repeat that":           ["Could you ask again?", "Tell me again.", "Repeat your question."],

            # ── WEATHER ────────────────────────────────────────────────────────
            # Full phrases kept — exact matches are safe.
            # Single-word "weather" removed (substring collision).
            "whats the weather":     ["I cannot check live weather yet.", "Weather access unavailable.", "No weather data right now."],
            "what's the weather":    ["I cannot check weather yet.", "Weather is not available.", "No weather data."],
            "is it going to rain":   ["I cannot check weather yet.", "No weather access.", "Check your weather app."],
            "how is the weather":    ["I cannot check weather.", "No weather access.", "Check your weather app."],
            "what is the weather":   ["I cannot check live weather yet.", "No weather data.", "Check your weather app."],

            # ── FUN EXTRAS ─────────────────────────────────────────────────────
            # "what is love" / "what is happiness" are kept — exact match is safe.
            # They are philosophy questions, not science questions.
            # "what is the meaning of life" kept — harmless exact phrase.
            "what is the meaning of life`": ["To exist and improve.", "42, according to some.", "A question worth exploring."],
            "do you believe in god":        ["That is a deep question.", "I am neutral on that.", "I respect all beliefs."],
            "what is love":                 ["A complex human emotion.", "A strong feeling of attachment.", "Hard to define."],
            "what is happiness":            ["A positive emotional state.", "Feeling content and satisfied.", "Depends on the person."],
            "tell me about yourself":       ["I am Thashu, a robot assistant created by Tharun. I can answer questions and assist you.", "I am Thashu, built to help."],
            "what year is it":              ["Check your device for the current date.", "I do not have live date access.", "Check your clock."],
            "what day is it":               ["Check your device for the date.", "I do not have live date access.", "Look at your calendar."],
        }

        # Pre-normalise all keys once at init for O(1) lookup at runtime.
        # Maps normalised_key → original responses list.
        self._lookup: dict[str, list[str]] = {
            self._normalise(k): v for k, v in self.data.items()
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(text: str) -> str:
        """
        Lowercase, strip punctuation, collapse whitespace.
        'How are you?' → 'how are you'
        'What's up!'  → 'whats up'
        """
        lowered = text.lower().strip()
        cleaned = ''.join(c for c in lowered if c.isalnum() or c.isspace())
        return ' '.join(cleaned.split())   # collapse multiple spaces

    # ── Public API (unchanged from original) ──────────────────────────────────

    def get_response(self, user_input: str) -> str | None:
        """
        Return a response if user_input exactly matches a known phrase
        after normalisation. Returns None otherwise.

        No partial matching. No substring matching. No fuzzy matching.
        If the normalised input is not an exact key, None is returned and
        the caller (Brain) routes to the AI engine.
        """
        key = self._normalise(user_input)
        responses = self._lookup.get(key)
        if responses:
            return random.choice(responses)
        return None

    # ── Preserved for external callers ────────────────────────────────────────

    def is_deep_question(self, text: str) -> bool:
        """
        Returns True if text contains a deep-question pattern.
        No longer used internally; preserved for Brain or other callers.
        """
        deep_patterns = [
            "what is", "what are", "how does", "how do",
            "why is", "why does", "define", "explain",
            "difference between", "meaning of", "tell me about",
            "how to", "how can", "what happens", "who invented",
            "when was", "where is", "which is"
        ]
        normalised = self._normalise(text)
        return any(p in normalised for p in deep_patterns)