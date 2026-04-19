import os, re

def transcribe_audio(file_path: str) -> tuple[str, float, list[str]]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if api_key:
        return _groq_transcribe(file_path, api_key)
    return _demo_transcript()

def _groq_transcribe(file_path: str, api_key: str):
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        with open(file_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
            )
        transcript = result.text.strip()
        duration = max(60.0, len(transcript.split()) / 2.5)
        return transcript, duration, _extract_words(transcript)
    except Exception as e:
        print(f"[WARNING] Groq transcription failed: {e} — using demo")
        return _demo_transcript()

def _demo_transcript():
    transcript = (
        "Um so I think my main strength is, uh, like problem solving. "
        "I basically love working with data and, um, I have experience "
        "building APIs and you know working in team environments. "
        "I think I am a good communicator and I basically enjoy working "
        "with teams. Uh I have worked on several projects and like I "
        "think they went well."
    )
    return transcript, 60.0, _extract_words(transcript)

def _extract_words(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\b[a-zA-Z']+\b", text)]