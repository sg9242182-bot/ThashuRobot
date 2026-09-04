class ShortTermMemory:
    def __init__(self, max_size=5):
        """
        Stores recent interactions
        
        Args:
            max_size (int): number of recent messages to keep
        """
        self.max_size = max_size
        self.memory = []

    def add(self, user_input: str, response: str):
        """
        Store a conversation pair
        """

        self.memory.append({
            "input": user_input,
            "response": response
        })

        # Keep memory size limited
        if len(self.memory) > self.max_size:
            self.memory.pop(0)

    def get_context(self):
        """
        Return recent conversation
        """
        return self.memory