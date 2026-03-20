"""
API endpoint tests.
Covers the full request/response cycle for every route.
"""
import json
import pytest


# ── Fixtures / helpers ────────────────────────────────────────────────────────

CONTRADICTION_PAYLOAD = {
    'test_run_id': 'run_001',
    'test_cases': [
        {
            'test_case_id': 'tc_001',
            'transcript': 'User: Hello\nAgent: Hi there, how can I help?',
            'conversation_path': 'greeting->response',
            'metrics': {
                'task_completion': 0.95,   # high
                'user_sentiment': -0.5,    # negative → contradiction
            },
            'metadata': {'scenario': 'test'},
        }
    ],
}

RANDOM_SAMPLE_PAYLOAD = {
    'test_run_id': 'run_002',
    'test_cases': [
        {
            'test_case_id': 'tc_002',
            'transcript': 'User: Thanks\nAgent: You are welcome',
            'conversation_path': 'greeting->close',
            'metrics': {'task_completion': 0.9, 'user_sentiment': 0.8},
        }
    ],
}


def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type='application/json')


def seed_transcript(client):
    """Send a metric-contradiction payload and return the queued transcript id."""
    post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    res = client.get('/api/transcripts/pending')
    transcripts = json.loads(res.data)
    assert len(transcripts) > 0
    return transcripts[0]['id']


# ── Webhook ───────────────────────────────────────────────────────────────────

def test_webhook_returns_success(client):
    res = post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    assert res.status_code == 200
    body = json.loads(res.data)
    assert body['status'] == 'success'
    assert body['test_run_id'] == 'run_001'


def test_webhook_queues_metric_contradiction(client):
    res = post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    body = json.loads(res.data)
    assert body['transcripts_queued'] == 1


def test_webhook_deduplication(client):
    post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    res = post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    body = json.loads(res.data)
    assert body['transcripts_queued'] == 0  # second call queues nothing


def test_webhook_skips_entry_with_no_transcript(client):
    payload = {
        'test_run_id': 'run_003',
        'test_cases': [
            {
                'test_case_id': 'tc_003',
                # no 'transcript' key
                'metrics': {'task_completion': 0.95, 'user_sentiment': -0.5},
            }
        ],
    }
    res = post_json(client, '/api/webhook/test-complete', payload)
    assert res.status_code == 200
    body = json.loads(res.data)
    assert body['transcripts_queued'] == 0


def test_webhook_malformed_body_returns_400(client):
    res = client.post(
        '/api/webhook/test-complete',
        data='not json',
        content_type='application/json',
    )
    assert res.status_code == 400


def test_webhook_missing_test_run_id_returns_400(client):
    res = post_json(client, '/api/webhook/test-complete', {'test_cases': []})
    assert res.status_code == 400


# ── Pending transcripts ───────────────────────────────────────────────────────

def test_pending_transcripts_empty(client):
    res = client.get('/api/transcripts/pending')
    assert res.status_code == 200
    assert json.loads(res.data) == []


def test_pending_transcripts_returns_queued(client):
    post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    res = client.get('/api/transcripts/pending')
    transcripts = json.loads(res.data)
    assert len(transcripts) == 1
    assert transcripts[0]['trigger_type'] == 'metric_contradiction'


def test_pending_transcripts_filter_by_trigger_type(client):
    post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    res = client.get('/api/transcripts/pending?trigger_type=edge_case')
    assert json.loads(res.data) == []

    res = client.get('/api/transcripts/pending?trigger_type=metric_contradiction')
    assert len(json.loads(res.data)) == 1


def test_pending_transcripts_pagination(client):
    post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    res = client.get('/api/transcripts/pending?page=1&per_page=1')
    assert len(json.loads(res.data)) == 1

    res = client.get('/api/transcripts/pending?page=2&per_page=1')
    assert json.loads(res.data) == []


# ── Annotate ──────────────────────────────────────────────────────────────────

def test_annotate_saves_and_generates_test_cases(client):
    tid = seed_transcript(client)
    res = post_json(client, f'/api/transcripts/{tid}/annotate', {
        'naturalness_score': 3,
        'intent_understanding_score': 4,
        'recovery_score': 2,
        'tone_score': 5,
        'failure_modes': ['agent_repeated', 'missed_context'],
        'notes': 'sounded robotic',
        'reviewer_id': 'tester',
    })
    assert res.status_code == 200
    body = json.loads(res.data)
    assert body['test_cases_generated'] == 2


def test_annotate_removes_from_pending(client):
    tid = seed_transcript(client)
    post_json(client, f'/api/transcripts/{tid}/annotate', {
        'naturalness_score': 1, 'intent_understanding_score': 1,
        'recovery_score': 1, 'tone_score': 1,
        'failure_modes': [], 'reviewer_id': 'tester',
    })
    res = client.get('/api/transcripts/pending')
    assert json.loads(res.data) == []


def test_annotate_rejects_score_out_of_range(client):
    tid = seed_transcript(client)
    res = post_json(client, f'/api/transcripts/{tid}/annotate', {
        'naturalness_score': 99,   # invalid
        'intent_understanding_score': 1,
        'recovery_score': 1,
        'tone_score': 1,
    })
    assert res.status_code == 400


def test_annotate_malformed_body_returns_400(client):
    tid = seed_transcript(client)
    res = client.post(
        f'/api/transcripts/{tid}/annotate',
        data='not json',
        content_type='application/json',
    )
    assert res.status_code == 400


# ── Defer ─────────────────────────────────────────────────────────────────────

def test_defer_removes_from_pending_then_reappears(client):
    post_json(client, '/api/webhook/test-complete', CONTRADICTION_PAYLOAD)
    tid = json.loads(client.get('/api/transcripts/pending').data)[0]['id']

    res = post_json(client, f'/api/transcripts/{tid}/defer', {})
    assert res.status_code == 200

    # deferred transcripts still show up in pending (review_status IN pending, deferred)
    transcripts = json.loads(client.get('/api/transcripts/pending').data)
    assert any(t['id'] == tid for t in transcripts)


# ── Staging / approve ─────────────────────────────────────────────────────────

def test_staging_empty_initially(client):
    res = client.get('/api/test-cases/staging')
    assert json.loads(res.data) == []


def test_staging_populated_after_annotation_with_failure_modes(client):
    tid = seed_transcript(client)
    post_json(client, f'/api/transcripts/{tid}/annotate', {
        'naturalness_score': 1, 'intent_understanding_score': 1,
        'recovery_score': 1, 'tone_score': 1,
        'failure_modes': ['tone_too_formal'],
        'reviewer_id': 'tester',
    })
    res = client.get('/api/test-cases/staging')
    cases = json.loads(res.data)
    assert len(cases) == 1
    assert cases[0]['failure_mode'] == 'tone_too_formal'


def test_approve_test_case(client):
    tid = seed_transcript(client)
    post_json(client, f'/api/transcripts/{tid}/annotate', {
        'naturalness_score': 1, 'intent_understanding_score': 1,
        'recovery_score': 1, 'tone_score': 1,
        'failure_modes': ['agent_repeated'],
        'reviewer_id': 'tester',
    })
    case_id = json.loads(client.get('/api/test-cases/staging').data)[0]['id']

    res = post_json(client, f'/api/test-cases/{case_id}/approve', {})
    assert res.status_code == 200

    # no longer in staging
    assert json.loads(client.get('/api/test-cases/staging').data) == []


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_stats_structure(client):
    res = client.get('/api/stats')
    assert res.status_code == 200
    body = json.loads(res.data)
    assert 'status_counts' in body
    assert 'trigger_counts' in body
    assert 'failure_mode_counts' in body
    assert 'test_cases_generated' in body


def test_stats_counts_after_workflow(client):
    tid = seed_transcript(client)
    post_json(client, f'/api/transcripts/{tid}/annotate', {
        'naturalness_score': 2, 'intent_understanding_score': 2,
        'recovery_score': 2, 'tone_score': 2,
        'failure_modes': ['agent_repeated'],
        'reviewer_id': 'tester',
    })
    body = json.loads(client.get('/api/stats').data)
    assert body['status_counts'].get('reviewed', 0) == 1
    assert body['test_cases_generated'] == 1
    assert body['failure_mode_counts'].get('agent_repeated', 0) == 1
