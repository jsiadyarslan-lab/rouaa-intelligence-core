"""Source health — states carried from pipeline_state.py (KEEP)."""
from __future__ import annotations

ORDER = ["PENDING", "ACCESSIBLE", "DOCUMENTED", "EXTRACTED", "PUBLISHABLE"]
TERMINAL = {"BLOCKED", "FAILED"}


class SourceHealth:
    def __init__(self, store, source_id: str):
        self.store, self.source_id = store, source_id
        self.state = "PENDING"

    def transition(self, new_state: str, reason: str = "") -> str:
        if self.state in TERMINAL:
            return self.state                      # terminal stays (isolation)
        if new_state in TERMINAL:
            self.state = new_state
        else:
            idx = ORDER.index(new_state) if new_state in ORDER else -1
            if idx > ORDER.index(self.state) if self.state in ORDER else False:
                self.state = new_state
        self.store.audit("SOURCE_STATE", {"source_id": self.source_id,
                                          "state": self.state, "reason": reason})
        return self.state
