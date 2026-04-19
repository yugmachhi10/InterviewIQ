from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from services.transcriber import transcribe_audio
from services.analyzer import analyze_interview
import tempfile, os

router = APIRouter()

ALLOWED = {".wav", ".mp3", ".mp4", ".m4a", ".ogg", ".flac", ".webm"}

@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    role: str            = Form(default=""),
    interview_type: str  = Form(default=""),
    round: str           = Form(default=""),
    format: str          = Form(default=""),
    tier: str            = Form(default=""),
    experience: str      = Form(default=""),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"File type {ext} not supported. Use: {ALLOWED}")

    # Save upload to temp file
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        transcript, duration_seconds, word_list = transcribe_audio(tmp_path)
        result = analyze_interview(
            transcript=transcript,
            word_list=word_list,
            duration_seconds=duration_seconds,
            role=role,
            interview_type=interview_type,
            round=round,
            format=format,
            tier=tier,
            experience=experience,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)