"""GoCollect fair value client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import GOCOLLECT, GoCollectConfig


@dataclass(frozen=True)
class FairValue:
    title: str
    issue_number: str
    grade: float
    value: float
    source: str


class GoCollectClient:
    def __init__(self, config: GoCollectConfig = GOCOLLECT) -> None:
        self.config = config

    def fetch_fair_value(self, title: str, issue_number: str, grade: float) -> Optional[FairValue]:
        """Return GoCollect fair market value for a comic/grade.

        TODO: Add GoCollect authentication once the account type and token
        exchange flow are confirmed.
        TODO: Map the exact GoCollect comic search and graded FMV endpoints.
        The public documentation and plan-specific API shape are not stable
        enough to hard-code here without credentials.
        """

        if not self.config.api_key:
            return None

        # Placeholder until endpoint mapping is confirmed. Keep this method as
        # the single integration point so the GUI/database layers do not change.
        return None
