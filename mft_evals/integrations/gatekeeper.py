"""
MFT Eval Platform - Gatekeeper Integration

Associates each eval with a Gatekeeper (GK) feature flag and Phabricator
task, creating the code ↔ eval ↔ feature association chain.

How this works:
  1. Each eval config includes a `gk_name` and `task_id`
  2. The GK gates the feature that the eval validates
  3. When the eval runs (in CI or scheduled), results are tagged with the GK
  4. This allows tracing: GK → eval → scores → launch decision

Usage:
    # In eval YAML config:
    launch:
      gk_name: mft_payment_extraction_v2
      task_id: T123456789
      diff_ids: [D987654321]
      feature_name: Payment Metadata Extraction

    # In Python:
    gk_config = GatekeeperConfig.from_eval_config(eval_config)
    if gk_config.is_gated():
        # Check if feature is enabled before running eval
        enabled = gk_config.check()

GK Best Practices (from Meta's gating docs):
  - Always use GK for user-facing feature changes
  - GK name should match the eval name for easy tracing
  - Remove GK after full rollout (eval remains for regression monitoring)
  - Use JustKnob (JK) for backend-only infra changes, not GK
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GatekeeperConfig:
    """
    Gatekeeper configuration that links an eval to its feature flag.

    This creates the association:
      Code (diff) → GK (feature flag) → Eval (quality gate) → Launch (ship decision)
    """

    gk_name: str = ""
    task_id: str = ""
    diff_ids: List[str] = field(default_factory=list)
    feature_name: str = ""
    team: str = ""

    def is_gated(self) -> bool:
        """Returns True if this eval is associated with a GK."""
        return bool(self.gk_name)

    def check(self, user_id: Optional[int] = None) -> bool:
        """
        Check if the associated GK is enabled.

        In production, this calls Meta's Gatekeeper API.
        In local dev, defaults to True (feature assumed enabled).
        """
        if not self.gk_name:
            return True

        try:
            from gatekeeper import GK

            return GK.check(self.gk_name, user_id=user_id)
        except ImportError:
            logger.debug(
                f"GK client unavailable (local dev), assuming '{self.gk_name}' is enabled"
            )
            return True

    def gk_url(self) -> str:
        """Return the internal URL for this GK's project page."""
        if not self.gk_name:
            return ""
        return f"https://www.internalfb.com/intern/gatekeeper/projects/{self.gk_name}/"

    def task_url(self) -> str:
        """Return the internal URL for the associated task."""
        if not self.task_id:
            return ""
        task_num = self.task_id.lstrip("T")
        return f"https://www.internalfb.com/tasks?t={task_num}"

    def diff_urls(self) -> List[str]:
        """Return internal URLs for associated diffs."""
        urls = []
        for diff_id in self.diff_ids:
            diff_num = diff_id.lstrip("D")
            urls.append(f"https://www.internalfb.com/diff/D{diff_num}")
        return urls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gk_name": self.gk_name,
            "task_id": self.task_id,
            "diff_ids": self.diff_ids,
            "feature_name": self.feature_name,
            "team": self.team,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatekeeperConfig":
        return cls(
            gk_name=data.get("gk_name", ""),
            task_id=data.get("task_id", ""),
            diff_ids=data.get("diff_ids", []),
            feature_name=data.get("feature_name", ""),
            team=data.get("team", ""),
        )

    @classmethod
    def from_eval_config(cls, eval_config) -> "GatekeeperConfig":
        """Extract GK config from an EvalConfig's launch metadata."""
        launch = getattr(eval_config, "launch", None)
        if launch and isinstance(launch, dict):
            return cls.from_dict(launch)
        if launch and isinstance(launch, GatekeeperConfig):
            return launch
        # Fall back to individual fields
        return cls(
            gk_name=getattr(eval_config, "gk_name", ""),
            task_id=getattr(eval_config, "task_id", ""),
            team=getattr(eval_config, "owner", None) and eval_config.owner.team or "",
        )
