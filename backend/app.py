"""
eval-review-queue
Entry point — run with: python backend/app.py

Module layout:
  database.py  — SQLite connection management and schema
  selector.py  — TranscriptSelector: which transcripts need review and why
  generator.py — TestCaseGenerator: builds test configs from failure modes
  routes.py    — Flask app and all API endpoints
"""
import os
import sys

# Ensure sibling modules (database, selector, generator, routes) are importable
# regardless of the working directory the process is launched from.
sys.path.insert(0, os.path.dirname(__file__))

from routes import app          # noqa: E402  (import after sys.path setup)
from database import init_db    # noqa: E402

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
