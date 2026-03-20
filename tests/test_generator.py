"""
Unit tests for TestCaseGenerator.
No Flask context needed — pure logic.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from generator import TestCaseGenerator
except ImportError:
    from app import TestCaseGenerator

CONTEXT = {
    'conversation_path': 'greeting->response',
    'user_utterance': 'Can you help me?',
    'agent_response': 'Sure!',
}


class TestKnownFailureModes:
    def test_agent_repeated(self):
        result = TestCaseGenerator.generate('agent_repeated', CONTEXT)
        assert result['template'] == 'Test agent response consistency'
        assert result['config']['check_type'] == 'repetition_detection'

    def test_misunderstood_clarification(self):
        result = TestCaseGenerator.generate('misunderstood_clarification', CONTEXT)
        assert result['config']['check_type'] == 'intent_understanding'

    def test_tone_too_formal(self):
        result = TestCaseGenerator.generate('tone_too_formal', CONTEXT)
        assert result['config']['expected_tone'] == 'conversational'

    def test_interrupted_poorly(self):
        result = TestCaseGenerator.generate('interrupted_poorly', CONTEXT)
        assert result['config']['check_type'] == 'barge_in_response'

    def test_completed_wrong_task(self):
        result = TestCaseGenerator.generate('completed_wrong_task', CONTEXT)
        assert result['config']['verify_intent'] is True


class TestUnknownFailureMode:
    def test_returns_generic_template(self):
        result = TestCaseGenerator.generate('some_new_failure', CONTEXT)
        assert 'some_new_failure' in result['template']
        assert result['config']['check_type'] == 'manual_review_required'

    def test_generic_includes_assertion(self):
        result = TestCaseGenerator.generate('weird_failure', CONTEXT)
        assert 'weird_failure' in result['config']['assertion']


class TestContextEnrichment:
    def test_source_context_attached(self):
        result = TestCaseGenerator.generate('agent_repeated', CONTEXT)
        assert 'source_context' in result['config']
        assert result['config']['source_context']['conversation_path'] == CONTEXT['conversation_path']

    def test_source_context_with_empty_context(self):
        result = TestCaseGenerator.generate('agent_repeated', {})
        assert result['config']['source_context']['conversation_path'] is None

    def test_original_config_not_mutated(self):
        """generate() should not modify the class-level template dict."""
        before = TestCaseGenerator.FAILURE_MODE_TEMPLATES['agent_repeated']['config'].copy()
        TestCaseGenerator.generate('agent_repeated', CONTEXT)
        after = TestCaseGenerator.FAILURE_MODE_TEMPLATES['agent_repeated']['config']
        assert before == after
