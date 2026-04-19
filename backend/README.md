# Interview Analyzer — Backend

## Folder Structure
```
backend/
├── main.py                  # FastAPI app entry point
├── requirements.txt
├── .env.example             # Copy to .env and add your API key
├── routes/
│   └── analyze.py           # POST /analyze endpoint
└── services/
    ├── transcriber.py       # Audio → text (Whisper API or local)
    ├── analyzer.py          # Text → AI analysis (OpenAI / Anthropic)
    └── scorer.py            # Local fallback scoring (no API needed)
```

## Setup (takes ~2 minutes)

```bash
# 1. Go into backend folder
cd backend

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Add your API key
cp .env.example .env
# Open .env and paste your OPENAI_API_KEY or ANTHROPIC_API_KEY

# 6. Run the server
uvicorn main:app --reload --port 8000
```

## Test it works
Open browser → http://127.0.0.1:8000
You should see: {"message": "Interview Analyzer API is running ✅"}

Then open your index.html frontend and click Ping — it should say Connected!

## API

### POST /analyze
**Form data:**
- `file` — audio file (.wav, .mp3, .m4a, etc.)
- `role` — job role (optional)
- `interview_type` — type of interview (optional)
- `round`, `format`, `tier`, `experience` — optional context

**Returns:**
```json
{
  "overall_score": 7,
  "summary": "...",
  "total_fillers": 12,
  "long_pauses": 2,
  "confidence_drops": 3,
  "filler_words": [{"word": "um", "count": 5}],
  "questions": [...],
  "weaknesses": [...],
  "improvement_plan": [...]
}
```

## Works without API keys!
Without an API key, the app uses local rule-based scoring.
With OPENAI_API_KEY → uses GPT-4o-mini for AI analysis + Whisper for transcription.
With ANTHROPIC_API_KEY → uses Claude Haiku for AI analysis.
