"""
API routes and Flask app initialisation.
"""
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from database import get_db, close_db
from selector import TranscriptSelector
from generator import TestCaseGenerator

app = Flask(__name__, template_folder='../frontend', static_folder='../frontend/static')
CORS(app)
app.teardown_appcontext(close_db)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/webhook/test-complete', methods=['POST'])
def webhook_test_complete():
    """
    Receive test results from an eval platform.

    Expected payload:
    {
        "test_run_id": "run_abc123",
        "test_cases": [
            {
                "test_case_id": "test_001",
                "transcript": "User: Hello\\nAgent: Hi, how can I help?",
                "audio_url": "https://...",
                "conversation_path": "greeting->intent_capture->response",
                "metrics": { "task_completion": 0.95, "user_sentiment": -0.4, ... },
                "metadata": { "test_scenario": "angry_customer" }
            }
        ]
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400

    test_run_id = data.get('test_run_id')
    if not test_run_id:
        return jsonify({'error': 'Missing required field: test_run_id'}), 400

    conn = get_db()
    added_count = 0

    for test_case in data.get('test_cases', []):
        transcript_text = test_case.get('transcript')
        if not transcript_text:
            continue

        metrics = test_case.get('metrics', {})
        conversation_path = test_case.get('conversation_path', '')

        selector = TranscriptSelector(metrics, conversation_path)
        should_review, trigger_type, trigger_reason = selector.should_review()

        if not should_review:
            continue

        existing = conn.execute(
            'SELECT id FROM transcripts WHERE test_run_id = ? AND test_case_id = ?',
            (test_run_id, test_case.get('test_case_id'))
        ).fetchone()
        if existing:
            continue

        conn.execute('''
            INSERT INTO transcripts
            (test_run_id, test_case_id, conversation_path, audio_url,
             transcript_text, metadata, metrics, trigger_type, trigger_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            test_run_id,
            test_case.get('test_case_id'),
            conversation_path,
            test_case.get('audio_url'),
            transcript_text,
            json.dumps(test_case.get('metadata', {})),
            json.dumps(metrics),
            trigger_type,
            trigger_reason,
        ))
        added_count += 1

    conn.commit()
    return jsonify({'status': 'success', 'test_run_id': test_run_id, 'transcripts_queued': added_count})


@app.route('/api/transcripts/<int:transcript_id>/defer', methods=['POST'])
def defer_transcript(transcript_id):
    """Defer a transcript for later review."""
    conn = get_db()
    conn.execute(
        "UPDATE transcripts SET review_status = 'deferred' WHERE id = ?",
        (transcript_id,)
    )
    conn.commit()
    return jsonify({'status': 'success', 'transcript_id': transcript_id})


@app.route('/api/transcripts/pending', methods=['GET'])
def get_pending_transcripts():
    """
    List pending and deferred transcripts (paginated).

    Query params:
      page         int  default 1
      per_page     int  default 50
      trigger_type str  optional — metric_contradiction | edge_case | random_sample
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    trigger_filter = request.args.get('trigger_type')
    offset = (page - 1) * per_page

    where = "WHERE t.review_status IN ('pending', 'deferred')"
    params = []
    if trigger_filter:
        where += ' AND t.trigger_type = ?'
        params.append(trigger_filter)
    params.extend([per_page, offset])

    conn = get_db()
    rows = conn.execute(f'''
        SELECT t.*, a.id as annotation_id
        FROM transcripts t
        LEFT JOIN annotations a ON t.id = a.transcript_id
        {where}
        ORDER BY t.review_status ASC, t.created_at DESC
        LIMIT ? OFFSET ?
    ''', params).fetchall()

    return jsonify([{
        'id': row['id'],
        'test_run_id': row['test_run_id'],
        'test_case_id': row['test_case_id'],
        'conversation_path': row['conversation_path'],
        'audio_url': row['audio_url'],
        'transcript_text': row['transcript_text'],
        'metadata': json.loads(row['metadata']) if row['metadata'] else {},
        'metrics': json.loads(row['metrics']) if row['metrics'] else {},
        'trigger_type': row['trigger_type'],
        'trigger_reason': row['trigger_reason'],
        'created_at': row['created_at'],
        'has_annotation': row['annotation_id'] is not None,
    } for row in rows])


@app.route('/api/transcripts/<int:transcript_id>/annotate', methods=['POST'])
def annotate_transcript(transcript_id):
    """
    Save annotation for a transcript.

    Expected payload:
    {
        "naturalness_score": 1-5,
        "intent_understanding_score": 1-5,
        "recovery_score": 1-5,
        "tone_score": 1-5,
        "failure_modes": ["mode1", "mode2"],
        "notes": "...",
        "reviewer_id": "..."
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400

    score_fields = [
        'naturalness_score', 'intent_understanding_score',
        'recovery_score', 'tone_score',
    ]
    for field in score_fields:
        val = data.get(field)
        if val is not None and not (isinstance(val, int) and 1 <= val <= 5):
            return jsonify({'error': f'{field} must be an integer between 1 and 5'}), 400

    conn = get_db()
    conn.execute('''
        INSERT INTO annotations
        (transcript_id, naturalness_score, intent_understanding_score,
         recovery_score, tone_score, failure_modes, notes, reviewer_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        transcript_id,
        data.get('naturalness_score'),
        data.get('intent_understanding_score'),
        data.get('recovery_score'),
        data.get('tone_score'),
        json.dumps(data.get('failure_modes', [])),
        data.get('notes'),
        data.get('reviewer_id', 'anonymous'),
    ))

    conn.execute(
        "UPDATE transcripts SET review_status = 'reviewed' WHERE id = ?",
        (transcript_id,)
    )

    failure_modes = data.get('failure_modes', [])
    if failure_modes:
        row = conn.execute(
            'SELECT * FROM transcripts WHERE id = ?', (transcript_id,)
        ).fetchone()
        if row:
            context = {
                'conversation_path': row['conversation_path'],
                'transcript': row['transcript_text'],
            }
            for mode in failure_modes:
                tc = TestCaseGenerator.generate(mode, context)
                conn.execute('''
                    INSERT INTO generated_test_cases
                    (source_transcript_id, failure_mode, test_case_template, test_case_config)
                    VALUES (?, ?, ?, ?)
                ''', (transcript_id, mode, tc['template'], json.dumps(tc['config'])))

    conn.commit()
    return jsonify({
        'status': 'success',
        'transcript_id': transcript_id,
        'test_cases_generated': len(failure_modes),
    })


@app.route('/api/test-cases/staging', methods=['GET'])
def get_staging_test_cases():
    """List generated test cases awaiting approval."""
    conn = get_db()
    rows = conn.execute('''
        SELECT tc.*, t.test_case_id as source_test_case, t.transcript_text as source_transcript
        FROM generated_test_cases tc
        JOIN transcripts t ON tc.source_transcript_id = t.id
        WHERE tc.status = 'staging'
        ORDER BY tc.created_at DESC
    ''').fetchall()

    return jsonify([{
        'id': row['id'],
        'failure_mode': row['failure_mode'],
        'template': row['test_case_template'],
        'config': json.loads(row['test_case_config']),
        'source_test_case': row['source_test_case'],
        'source_transcript': row['source_transcript'],
        'created_at': row['created_at'],
    } for row in rows])


@app.route('/api/test-cases/<int:test_case_id>/approve', methods=['POST'])
def approve_test_case(test_case_id):
    """Approve a staged test case."""
    conn = get_db()
    conn.execute(
        "UPDATE generated_test_cases SET status = 'approved' WHERE id = ?",
        (test_case_id,)
    )
    conn.commit()
    return jsonify({'status': 'success', 'test_case_id': test_case_id})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Review queue statistics."""
    conn = get_db()

    status_counts = {
        row['review_status']: row['count']
        for row in conn.execute(
            'SELECT review_status, COUNT(*) as count FROM transcripts GROUP BY review_status'
        ).fetchall()
    }

    trigger_counts = {
        row['trigger_type']: row['count']
        for row in conn.execute(
            'SELECT trigger_type, COUNT(*) as count FROM transcripts GROUP BY trigger_type'
        ).fetchall()
    }

    failure_mode_counts = {}
    for row in conn.execute(
        'SELECT failure_modes FROM annotations WHERE failure_modes IS NOT NULL'
    ).fetchall():
        for mode in json.loads(row['failure_modes']):
            failure_mode_counts[mode] = failure_mode_counts.get(mode, 0) + 1

    test_cases_generated = conn.execute(
        'SELECT COUNT(*) as count FROM generated_test_cases'
    ).fetchone()['count']

    return jsonify({
        'status_counts': status_counts,
        'trigger_counts': trigger_counts,
        'failure_mode_counts': failure_mode_counts,
        'test_cases_generated': test_cases_generated,
    })
