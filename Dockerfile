FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create directory for database
RUN mkdir -p /data

# Set environment variables
ENV FLASK_APP=backend/app.py
ENV PORT=5001
ENV DATABASE=/data/review_queue.db

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/api/stats')" || exit 1

# Run application
CMD ["python", "backend/app.py"]
