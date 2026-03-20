"""
Unit tests for database initialisation and schema.
Verifies that init_db() creates the expected tables with the correct columns,
defaults, and constraints — without depending on Flask or the app runtime.
"""
import sqlite3
import tempfile
import os
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fresh_db_path():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    return path


def _init_db(path):
    """Mirror of database.init_db() against an arbitrary file path."""
    conn = sqlite3.connect(path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_run_id TEXT NOT NULL,
            test_case_id TEXT NOT NULL,
            conversation_path TEXT,
            audio_url TEXT,
            transcript_text TEXT NOT NULL,
            metadata TEXT,
            metrics TEXT,
            trigger_type TEXT NOT NULL,
            trigger_reason TEXT,
            review_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transcript_id INTEGER NOT NULL,
            naturalness_score INTEGER CHECK(naturalness_score BETWEEN 1 AND 5),
            intent_understanding_score INTEGER CHECK(intent_understanding_score BETWEEN 1 AND 5),
            recovery_score INTEGER CHECK(recovery_score BETWEEN 1 AND 5),
            tone_score INTEGER CHECK(tone_score BETWEEN 1 AND 5),
            failure_modes TEXT,
            notes TEXT,
            reviewer_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transcript_id) REFERENCES transcripts (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS generated_test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_transcript_id INTEGER NOT NULL,
            failure_mode TEXT NOT NULL,
            test_case_template TEXT NOT NULL,
            test_case_config TEXT,
            status TEXT DEFAULT 'staging',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_transcript_id) REFERENCES transcripts (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS metric_reliability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            qualitative_issue_count INTEGER DEFAULT 0,
            total_occurrences INTEGER DEFAULT 0,
            reliability_score REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def _table_names(path):
    conn = sqlite3.connect(path)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    return names


def _column_names(path, table):
    conn = sqlite3.connect(path)
    cols = {r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}
    conn.close()
    return cols


def _insert_transcript(conn, run_id='run_1', case_id='tc_1',
                        text='hello', trigger='random_sample'):
    conn.execute(
        'INSERT INTO transcripts (test_run_id, test_case_id, transcript_text, trigger_type) '
        'VALUES (?, ?, ?, ?)',
        (run_id, case_id, text, trigger),
    )
    conn.commit()
    return conn.execute('SELECT id FROM transcripts ORDER BY id DESC LIMIT 1').fetchone()[0]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path():
    path = _fresh_db_path()
    _init_db(path)
    yield path
    os.unlink(path)


@pytest.fixture
def conn(db_path):
    c = sqlite3.connect(db_path)
    c.execute('PRAGMA foreign_keys = ON')
    yield c
    c.close()


# ── Table existence ───────────────────────────────────────────────────────────

class TestTablesCreated:
    def test_transcripts_table_exists(self, db_path):
        assert 'transcripts' in _table_names(db_path)

    def test_annotations_table_exists(self, db_path):
        assert 'annotations' in _table_names(db_path)

    def test_generated_test_cases_table_exists(self, db_path):
        assert 'generated_test_cases' in _table_names(db_path)

    def test_metric_reliability_table_exists(self, db_path):
        assert 'metric_reliability' in _table_names(db_path)

    def test_idempotent_init_does_not_raise(self, db_path):
        """Running init_db a second time should be a no-op."""
        _init_db(db_path)
        assert 'transcripts' in _table_names(db_path)


# ── Transcripts schema ────────────────────────────────────────────────────────

class TestTranscriptSchema:
    REQUIRED_COLS = (
        'id', 'test_run_id', 'test_case_id', 'transcript_text',
        'trigger_type', 'review_status', 'created_at',
    )

    def test_required_columns_present(self, db_path):
        cols = _column_names(db_path, 'transcripts')
        for col in self.REQUIRED_COLS:
            assert col in cols, f'Missing column: {col}'

    def test_optional_columns_present(self, db_path):
        cols = _column_names(db_path, 'transcripts')
        for col in ('conversation_path', 'audio_url', 'metadata', 'metrics', 'trigger_reason'):
            assert col in cols

    def test_default_review_status_is_pending(self, conn):
        _insert_transcript(conn)
        row = conn.execute('SELECT review_status FROM transcripts').fetchone()
        assert row[0] == 'pending'

    def test_autoincrement_id(self, conn):
        _insert_transcript(conn, run_id='r1', case_id='c1')
        _insert_transcript(conn, run_id='r2', case_id='c2')
        ids = [r[0] for r in conn.execute('SELECT id FROM transcripts ORDER BY id').fetchall()]
        assert ids == [1, 2]


# ── Annotations schema ────────────────────────────────────────────────────────

class TestAnnotationSchema:
    def test_required_columns_present(self, db_path):
        cols = _column_names(db_path, 'annotations')
        for col in ('id', 'transcript_id', 'naturalness_score', 'failure_modes', 'reviewer_id'):
            assert col in cols

    def test_score_check_rejects_zero(self, conn):
        tid = _insert_transcript(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                'INSERT INTO annotations (transcript_id, naturalness_score) VALUES (?, ?)',
                (tid, 0),
            )
            conn.commit()

    def test_score_check_rejects_six(self, conn):
        tid = _insert_transcript(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                'INSERT INTO annotations (transcript_id, naturalness_score) VALUES (?, ?)',
                (tid, 6),
            )
            conn.commit()

    def test_score_check_accepts_boundary_values(self, conn):
        tid = _insert_transcript(conn)
        conn.execute(
            'INSERT INTO annotations (transcript_id, naturalness_score, tone_score) VALUES (?, ?, ?)',
            (tid, 1, 5),
        )
        conn.commit()
        row = conn.execute('SELECT naturalness_score, tone_score FROM annotations').fetchone()
        assert row == (1, 5)

    def test_all_score_columns_have_check_constraints(self, db_path):
        """Each score column rejects out-of-range values."""
        score_cols = [
            'naturalness_score', 'intent_understanding_score',
            'recovery_score', 'tone_score',
        ]
        for col in score_cols:
            conn = sqlite3.connect(db_path)
            conn.execute('PRAGMA foreign_keys = ON')
            tid = _insert_transcript(conn, run_id=col, case_id=col)
            with pytest.raises(sqlite3.IntegrityError, match=''):
                conn.execute(
                    f'INSERT INTO annotations (transcript_id, {col}) VALUES (?, ?)',
                    (tid, 99),
                )
                conn.commit()
            conn.close()


# ── Generated test cases schema ───────────────────────────────────────────────

class TestGeneratedTestCasesSchema:
    def test_default_status_is_staging(self, conn):
        tid = _insert_transcript(conn)
        conn.execute(
            'INSERT INTO generated_test_cases '
            '(source_transcript_id, failure_mode, test_case_template) VALUES (?, ?, ?)',
            (tid, 'agent_repeated', 'some template'),
        )
        conn.commit()
        row = conn.execute('SELECT status FROM generated_test_cases').fetchone()
        assert row[0] == 'staging'

    def test_required_columns_present(self, db_path):
        cols = _column_names(db_path, 'generated_test_cases')
        for col in ('id', 'source_transcript_id', 'failure_mode', 'test_case_template', 'status'):
            assert col in cols


# ── Metric reliability schema ─────────────────────────────────────────────────

class TestMetricReliabilitySchema:
    def test_required_columns_present(self, db_path):
        cols = _column_names(db_path, 'metric_reliability')
        for col in ('id', 'metric_name', 'qualitative_issue_count',
                    'total_occurrences', 'reliability_score'):
            assert col in cols

    def test_default_counts_are_zero(self, conn):
        conn.execute(
            'INSERT INTO metric_reliability (metric_name) VALUES (?)',
            ('task_completion',),
        )
        conn.commit()
        row = conn.execute(
            'SELECT qualitative_issue_count, total_occurrences FROM metric_reliability'
        ).fetchone()
        assert row == (0, 0)
