# Quickstart Guide

Get eval-review-queue running in 10 minutes.

## Prerequisites

- Python 3.9+
- pip
- Web browser

## Step 1: Install

```bash
cd eval-review-queue
pip install -r requirements.txt
```

## Step 2: Start Server

```bash
python backend/app.py
```

You should see:
```
* Running on http://0.0.0.0:5001
* Database initialized
```

## Step 3: Open Interface

Open your browser to: `http://localhost:5001`

You'll see the review queue dashboard (empty initially).

## Step 4: Send Test Data

Test the webhook with sample data:

```bash
curl -X POST http://localhost:5001/api/webhook/test-complete \
  -H "Content-Type: application/json" \
  -d '{
    "test_run_id": "test_run_001",
    "test_cases": [
      {
        "test_case_id": "horoscope_happy_path",
        "transcript": "User: Hi\nAgent: Hello! Welcome to Tech Horoscope. What'\''s your sign?\nUser: I'\''m a Virgo\nAgent: Ah, a Virgo! Let me see what the stars say... Your code will compile on the first try today, but only after you'\''ve already celebrated. The cloud gods smile upon you, but watch out for merge conflicts around 3pm. Remember: the best debugging happens when you explain your problem to a rubber duck.\nUser: Thanks!\nAgent: You'\''re welcome! Have a great day!",
        "audio_url": null,
        "conversation_path": "greeting->intent_capture->horoscope_generation->closing",
        "metrics": {
          "task_completion": 1.0,
          "user_sentiment": 0.8,
          "avg_latency": 0.9,
          "tool_correctness": 1.0,
          "conversation_progression": 0.95
        },
        "metadata": {
          "persona": "happy_user",
          "test_scenario": "standard_flow"
        }
      },
      {
        "test_case_id": "horoscope_confused_user",
        "transcript": "User: Hello\nAgent: Hi! I'\''m your Tech Horoscope agent. What zodiac sign are you?\nUser: What do you mean?\nAgent: What'\''s your zodiac sign?\nUser: I don'\''t understand\nAgent: Your zodiac sign - like Aries, Taurus, Gemini...\nUser: Oh! I'\''m a Libra\nAgent: Great! For Libra today: Your API calls will return 200 but your heart will return 404. The universe suggests pair programming, but your partner will have strong opinions about tabs vs spaces. A mysterious bug will reveal itself at 4:47pm.\nUser: Um, okay",
        "audio_url": null,
        "conversation_path": "greeting->intent_capture->clarification->clarification->intent_capture->horoscope_generation->closing",
        "metrics": {
          "task_completion": 0.9,
          "user_sentiment": -0.2,
          "avg_latency": 1.1,
          "tool_correctness": 1.0,
          "conversation_progression": 0.6,
          "user_repeat_rate": 0.4
        },
        "metadata": {
          "persona": "confused_user",
          "test_scenario": "clarification_needed"
        }
      },
      {
        "test_case_id": "horoscope_impatient_user",
        "transcript": "User: Hi give me my horoscope\nAgent: Hello! I'\''d be happy to help with your horoscope. First, what'\''s your zodiac sign?\nUser: Sagittarius\nAgent: Wonderful! Let me consult the stars for Sagittarius...\n[long pause]\nUser: Hello?\nAgent: Your tech horoscope for today: Your code review comments will be thorough but compassionate. A typo in your variable name will spark a 30-minute naming debate. The staging environment will work perfectly, but production will teach you humility.\nUser: Finally",
        "audio_url": null,
        "conversation_path": "greeting->intent_capture->horoscope_generation->closing",
        "metrics": {
          "task_completion": 1.0,
          "user_sentiment": -0.4,
          "avg_latency": 2.8,
          "tool_correctness": 1.0,
          "conversation_progression": 0.85,
          "user_repeat_rate": 0.2
        },
        "metadata": {
          "persona": "impatient_user",
          "test_scenario": "high_latency"
        }
      }
    ]
  }'
```

## Step 5: Review Transcripts

Refresh your browser. You should now see transcripts in the review queue:

1. **First transcript** (horoscope_happy_path): 
   - Won't be queued (passes all checks, not selected by random sampling)
   
2. **Second transcript** (horoscope_confused_user):
   - Queued as "metric_contradiction" (high task completion but negative sentiment)
   
3. **Third transcript** (horoscope_impatient_user):
   - Queued as "metric_contradiction" (high task completion, very negative sentiment, high latency but user repeated)

## Step 6: Annotate

For each transcript:

1. Click scores (1-5) for each dimension:
   - Naturalness: How human-like did the agent sound?
   - Intent Understanding: Did agent grasp what user wanted?
   - Recovery: How well did agent handle confusion?
   - Tone: Was the tone appropriate?

2. Select failure modes that apply:
   - For "confused_user": Select "misunderstood_clarification"
   - For "impatient_user": Select "interrupted_poorly" (user had to prompt)

3. Add notes (optional):
   - "Agent kept asking same question without trying alternative phrasing"
   - "Long pause made user think agent crashed"

4. Click "Submit Review"

## Step 7: Check Staging

Click "Staging Test Cases" tab.

You should see auto-generated test cases:
- **Test clarifying question handling** (from "misunderstood_clarification")
- **Test interruption handling** (from "interrupted_poorly")

Review the test case configs and click "Approve & Add to Suite" for good ones.

## Step 8: View Stats

The dashboard shows:
- Pending reviews
- Total reviewed
- Test cases generated
- Breakdown by trigger type

## Next Steps

### Connect to Your Eval Platform

Configure your platform to send webhooks to your server:

**Hamming.ai**: 
- Dashboard → Settings → Webhooks
- Add URL: `http://your-server:5001/api/webhook/test-complete`
- Event: `test_run_completed`

**Coval.dev**:
- Project Settings → Integrations
- Webhook URL: `http://your-server:5001/api/webhook/test-complete`
- Trigger: On test suite completion

**Custom Platform**:
See the webhook payload format in the README for reference

### Customize Sampling

Edit `backend/app.py`:

```python
class TranscriptSelector:
    def _check_metric_contradictions(self):
        # Adjust thresholds for your agent's baseline
        task_completion = self.metrics.get('task_completion', 0)
        sentiment = self.metrics.get('user_sentiment', 0)
        
        # Your agent might have different "normal" ranges
        if task_completion > 0.85 and sentiment < -0.25:
            return f'High completion but negative sentiment'
```

### Add Failure Modes

Edit `backend/app.py`:

```python
class TestCaseGenerator:
    FAILURE_MODE_TEMPLATES = {
        'your_custom_failure': {
            'template': 'Description of what to test',
            'config': {
                'check_type': 'your_evaluation_type',
                'assertion': 'What should pass'
            }
        }
    }
```

Add to frontend `index.html`:

```javascript
const FAILURE_MODES = [
    'agent_repeated',
    'your_custom_failure',  // Add here
    // ... rest
];
```

### Deploy to Production

For production use:

1. **Use real database**:
```bash
# Install PostgreSQL
pip install psycopg2-binary

# Update DATABASE constant in app.py
DATABASE = 'postgresql://user:pass@host/dbname'
```

2. **Add authentication**:
```python
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@app.route('/api/transcripts/pending')
@auth.login_required
def get_pending_transcripts():
    # ... existing code
```

3. **Deploy to cloud**:

Railway:
```bash
railway login
railway init
railway up
```

Heroku:
```bash
heroku create voice-agent-review
git push heroku main
```

AWS/GCP/Azure:
- Use Docker image (see `Dockerfile`)
- Deploy as container service

4. **Set up SSL** (required for webhooks from most platforms):
```bash
# Use Let's Encrypt or cloud provider SSL
# Configure reverse proxy (nginx/caddy)
```

## Troubleshooting

### Transcripts not appearing

**Check webhook is hitting server**:
```bash
# In app.py, add logging
@app.route('/api/webhook/test-complete', methods=['POST'])
def webhook_test_complete():
    print(f"Received webhook: {request.json}")
    # ... rest of code
```

**Check sampling logic**:
- Not all transcripts will be queued
- Random sampling is 10% (may not trigger with small samples)
- Verify metric values meet contradiction thresholds

### Database errors

**Initialize database**:
```bash
python -c "from backend.app import init_db; init_db()"
```

**Reset database**:
```bash
rm review_queue.db
python backend/app.py  # Will recreate
```

### Port already in use

```bash
# Change port in app.py
port = int(os.environ.get('PORT', 5002))  # Use 5002 instead

# Or kill process on port 5001
lsof -ti:5001 | xargs kill
```

### CORS errors

If accessing from different domain:

```python
# In app.py, adjust CORS config
CORS(app, origins=['https://your-frontend-domain.com'])
```

## Success Checklist

✅ Server running on port 5001  
✅ Dashboard loads in browser  
✅ Test webhook successfully queues transcripts  
✅ Can annotate and submit reviews  
✅ Test cases appear in staging  
✅ Stats update correctly  

You're ready to integrate with your eval platform!

## Getting Help

- See `README.md` for architecture and configuration details
- See `README.md` for API reference
- Open an issue on GitHub for bugs
- Customize freely - this is reference implementation

## Typical First-Week Workflow

**Day 1**: 
- Set up system
- Send test data
- Review 5-10 transcripts to understand interface

**Day 2-3**:
- Connect webhook from eval platform
- Run first real test suite
- Review 20 transcripts
- Calibrate sampling thresholds

**Day 4-5**:
- Review generated test cases
- Approve good ones
- Add custom failure modes
- Adjust annotation rubric

**Week 2+**:
- Regular review sessions (20-30 transcripts per deploy)
- Track which metrics are reliable
- Iterate on test case templates
- Build confidence in "ready to ship"

The first week is calibration. By week 2, you'll have a feedback loop running.
