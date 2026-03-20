"""
Unit tests for TranscriptSelector.
No Flask context needed — pure logic.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from selector import TranscriptSelector
except ImportError:
    from app import TranscriptSelector


class TestMetricContradictions:
    def test_high_completion_negative_sentiment(self):
        s = TranscriptSelector(
            {'task_completion': 0.9, 'user_sentiment': -0.4},
            'greeting->response'
        )
        should, trigger, reason = s.should_review()
        assert should is True
        assert trigger == 'metric_contradiction'
        assert 'sentiment' in reason

    def test_no_contradiction_when_both_positive(self):
        s = TranscriptSelector(
            {'task_completion': 0.9, 'user_sentiment': 0.5},
            'greeting->response'
        )
        # may still be random sampled; just check trigger type isn't contradiction
        _, trigger, _ = s.should_review()
        assert trigger != 'metric_contradiction'

    def test_high_tool_correctness_low_progression(self):
        s = TranscriptSelector(
            {'tool_correctness': 0.95, 'conversation_progression': 0.3},
            'greeting->tool->response'
        )
        should, trigger, _ = s.should_review()
        assert should is True
        assert trigger == 'metric_contradiction'

    def test_low_latency_high_repeat_rate(self):
        s = TranscriptSelector(
            {'avg_latency': 0.5, 'user_repeat_rate': 0.4},
            'greeting->response'
        )
        should, trigger, _ = s.should_review()
        assert should is True
        assert trigger == 'metric_contradiction'

    def test_below_threshold_not_flagged(self):
        s = TranscriptSelector(
            {'task_completion': 0.7, 'user_sentiment': -0.2},
            'greeting->response'
        )
        _, trigger, _ = s.should_review()
        assert trigger != 'metric_contradiction'


class TestEdgeCaseDetection:
    def test_many_unique_intents_flagged(self):
        path = 'a->b->c->d->e->f'  # 6 unique intents
        s = TranscriptSelector({}, path)
        should, trigger, _ = s.should_review()
        assert should is True
        assert trigger == 'edge_case'

    def test_few_intents_not_flagged_as_edge(self):
        s = TranscriptSelector({}, 'greeting->response->close')
        _, trigger, _ = s.should_review()
        assert trigger != 'edge_case'

    def test_empty_path_not_flagged(self):
        s = TranscriptSelector({}, '')
        _, trigger, _ = s.should_review()
        assert trigger != 'edge_case'

    def test_none_path_not_flagged(self):
        s = TranscriptSelector({}, None)
        _, trigger, _ = s.should_review()
        assert trigger != 'edge_case'


class TestRandomSampling:
    def test_random_sample_returns_bool(self):
        s = TranscriptSelector({}, 'greeting->response')
        result = s._random_sample()
        assert isinstance(result, bool)

    def test_roughly_ten_percent(self):
        """Over 1000 trials, ~10% should be sampled. Allow wide margin for CI."""
        s = TranscriptSelector({}, 'greeting->response')
        hits = sum(s._random_sample() for _ in range(1000))
        assert 30 < hits < 200  # 3%–20% — very loose, just checking it's not 0 or 100
