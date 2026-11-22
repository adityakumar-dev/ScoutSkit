"""A shared limit on what one run may spend, so a team of failing agents cannot burn tokens without end."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Budget:
    max_tokens: int
    spent: int = 0

    def spend(self, tokens: int) -> None:
        self.spent += max(0, tokens)

    @property
    def exhausted(self) -> bool:
        return self.max_tokens > 0 and self.spent >= self.max_tokens  # 0 means no limit


class Share:
    """One sub-agent's part of the run's budget: spending counts against both, and either running out stops it.
    A scout that burns its share leaves the rest for the sources that replace it."""

    def __init__(self, parent: Budget, tokens: int) -> None:
        self.parent, self.max_tokens, self.spent = parent, tokens, 0

    def spend(self, tokens: int) -> None:
        self.spent += max(0, tokens)
        self.parent.spend(tokens)

    @property
    def exhausted(self) -> bool:
        return self.parent.exhausted or (self.max_tokens > 0 and self.spent >= self.max_tokens)
