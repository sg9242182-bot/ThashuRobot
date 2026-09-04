import time


class AttentionSystem:
    def __init__(self):
        self.current_target = None
        self.last_switch_time = 0

        self.switch_cooldown = 1.5  # seconds
        self.lock_timeout = 3.0

        self.last_speaking_time = 0

    def update(self, persons, is_speaking):
        now = time.time()

        # 🔴 SAFETY: no persons at all
        if not persons:
            # Optional: release target after timeout
            if self.current_target and (now - self.last_switch_time > self.lock_timeout):
                self.current_target = None
            return self.current_target

        # Step 1: find owner
        owner = next((p for p in persons if p.get("is_owner")), None)

        # Step 2: speaking priority
        if is_speaking:
            self.last_speaking_time = now

            target = self._select_speaker(persons)

            if target and self._can_switch(now):
                self.current_target = target
                self.last_switch_time = now

        # Step 3: fallback to owner
        elif owner:
            if self._can_switch(now):
                self.current_target = owner
                self.last_switch_time = now

        # Step 4: fallback to closest person
        else:
            target = self._select_closest(persons)

            if target and self._can_switch(now):
                self.current_target = target
                self.last_switch_time = now

        return self.current_target

    def _can_switch(self, now):
        return (now - self.last_switch_time) > self.switch_cooldown

    def _select_speaker(self, persons):
        if not persons:
            return None

        # center-based selection
        return min(persons, key=lambda p: abs(p["center"][0] - 320))

    def _select_closest(self, persons):
        if not persons:
            return None

        return persons[0]