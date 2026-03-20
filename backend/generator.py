"""
Test case generation from annotated failure modes.
Each failure mode maps to a template config that can be fed into your eval platform.
"""
from typing import Dict


class TestCaseGenerator:
    """
    Generates structured test case configs from human-annotated failure modes.

    To add a custom failure mode, extend FAILURE_MODE_TEMPLATES with a new key.
    See README > Configuration > Failure Mode Templates.
    """

    FAILURE_MODE_TEMPLATES = {
        'agent_repeated': {
            'template': 'Test agent response consistency',
            'config': {
                'check_type': 'repetition_detection',
                'conversation_length': 'extended',
                'assertion': 'Agent should not repeat previous responses verbatim',
            },
        },
        'misunderstood_clarification': {
            'template': 'Test clarifying question handling',
            'config': {
                'check_type': 'intent_understanding',
                'inject_clarification': True,
                'assertion': 'Agent correctly interprets clarifying questions',
            },
        },
        'tone_too_formal': {
            'template': 'Test tone appropriateness',
            'config': {
                'check_type': 'tone_evaluation',
                'expected_tone': 'conversational',
                'assertion': 'Agent maintains appropriate casual tone',
            },
        },
        'interrupted_poorly': {
            'template': 'Test interruption handling',
            'config': {
                'check_type': 'barge_in_response',
                'interruption_timing': 'mid_sentence',
                'assertion': 'Agent stops speaking and acknowledges interruption',
            },
        },
        'completed_wrong_task': {
            'template': 'Test goal alignment',
            'config': {
                'check_type': 'task_correctness',
                'verify_intent': True,
                'assertion': 'Agent completes the actual requested task',
            },
        },
    }

    @classmethod
    def generate(cls, failure_mode: str, context: Dict) -> Dict:
        """
        Generate a test case config from a failure mode and conversation context.

        Unknown failure modes fall back to a generic manual-review template
        so no annotation is ever silently dropped.
        """
        if failure_mode not in cls.FAILURE_MODE_TEMPLATES:
            return {
                'template': f'Test for: {failure_mode}',
                'config': {
                    'check_type': 'manual_review_required',
                    'failure_context': context,
                    'assertion': f'Agent should not exhibit: {failure_mode}',
                },
            }

        template_data = cls.FAILURE_MODE_TEMPLATES[failure_mode]
        enriched_config = template_data['config'].copy()
        enriched_config['source_context'] = {
            'conversation_path': context.get('conversation_path'),
            'user_utterance': context.get('user_utterance'),
            'agent_response': context.get('agent_response'),
        }

        return {'template': template_data['template'], 'config': enriched_config}
