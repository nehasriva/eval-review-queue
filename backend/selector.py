"""
Transcript selection logic.
Determines which transcripts are surfaced for human review and why.
"""
import random
from typing import Dict, Optional


class TranscriptSelector:
    """
    Decides whether a transcript should enter the review queue.

    Three trigger types:
      - metric_contradiction: automated metrics disagree with each other
      - edge_case: conversation path is unusually complex
      - random_sample: baseline 10% sample for calibration
    """

    def __init__(self, metrics: Dict, conversation_path: str):
        self.metrics = metrics
        self.conversation_path = conversation_path

    def should_review(self) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Returns (should_review, trigger_type, trigger_reason).
        Checks triggers in priority order: contradiction > edge case > random.
        """
        contradiction = self._check_metric_contradictions()
        if contradiction:
            return True, 'metric_contradiction', contradiction

        if self._is_edge_case():
            return True, 'edge_case', f'Unusual path: {self.conversation_path}'

        if self._random_sample():
            return True, 'random_sample', 'Baseline sampling'

        return False, None, None

    def _check_metric_contradictions(self) -> Optional[str]:
        """
        Detects cases where metrics give conflicting quality signals.

        Thresholds are starting points — tune these for your domain.
        See README > Configuration > Sampling Thresholds.
        """
        task_completion = self.metrics.get('task_completion', 0)
        sentiment = self.metrics.get('user_sentiment', 0)
        if task_completion > 0.8 and sentiment < -0.3:
            return (
                f'High task completion ({task_completion:.2f}) '
                f'but negative sentiment ({sentiment:.2f})'
            )

        tool_correctness = self.metrics.get('tool_correctness', 0)
        conversation_progression = self.metrics.get('conversation_progression', 0)
        if tool_correctness > 0.9 and conversation_progression < 0.5:
            return (
                f'Correct tools ({tool_correctness:.2f}) '
                f'but poor progression ({conversation_progression:.2f})'
            )

        latency = self.metrics.get('avg_latency', 0)
        repeat_rate = self.metrics.get('user_repeat_rate', 0)
        if latency < 1.0 and repeat_rate > 0.3:
            return (
                f'Low latency ({latency:.2f}s) '
                f'but high repeats ({repeat_rate:.2f})'
            )

        return None

    def _is_edge_case(self) -> bool:
        """
        Heuristic: paths with more than 5 unique intents are unusual.
        In production, replace with a frequency-based check against historical paths.
        """
        if not self.conversation_path:
            return False
        return len(set(self.conversation_path.split('->'))) > 5

    def _random_sample(self) -> bool:
        """10% baseline sample. Adjust the rate in _random_sample() — see README."""
        return random.random() < 0.1
