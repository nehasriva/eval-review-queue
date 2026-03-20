"""
Database setup and connection management.
Uses Flask's g for request-scoped connections — auto-closed via teardown.
"""
import sqlite3
import os
from flask import g

DATABASE = os.environ.get('DATABASE', 'review_queue.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they don't exist. Called once at startup."""
    conn = sqlite3.connect(DATABASE)

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
