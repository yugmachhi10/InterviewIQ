import os, json, re
from services.scorer import compute_local_scores

FILLER_WORDS = ["um","uh","like","basically","actually","so","you know","right","mean","literally"]


# ──────────────────────────────────────────
# CHUNKING
# ──────────────────────────────────────────
def chunk_transcript_sentences(transcript, max_words=120):
    sentences = re.split(r'(?<=[.!?]) +', transcript)
    chunks = []
    current = ""
    for sentence in sentences:
        if len((current + " " + sentence).split()) <= max_words:
            current += " " + sentence
        else:
            if current.strip():
                chunks.append(current.strip())
            current = sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [transcript]


# ──────────────────────────────────────────
# MERGE
# ──────────────────────────────────────────
def merge_results(results):
    if not results:
        return None

    overall_score = sum(r.get("overall_score", 5) for r in results) // len(results)

    # Deduplicate summaries
    summaries = []
    seen_summaries = set()
    for r in results:
        s = r.get("summary", "").strip()
        if s and s not in seen_summaries:
            seen_summaries.add(s)
            summaries.append(s)

    # Deduplicate weaknesses
    weaknesses = []
    seen_weak = set()
    for r in results:
        for w in r.get("weaknesses", []):
            name = w.get("name", "").strip()
            if name and name not in seen_weak:
                seen_weak.add(name)
                weaknesses.append(w)

    # Deduplicate improvement plan
    plans = []
    seen_plans = set()
    for r in results:
        for p in r.get("improvement_plan", []):
            goal = p.get("goal", "").strip()
            if goal and goal not in seen_plans:
                seen_plans.add(goal)
                plans.append(p)

    return {
        "overall_score": overall_score,
        "summary": " ".join(summaries[:2]),
        "total_fillers": results[0].get("total_fillers", 0),
        "long_pauses": sum(r.get("long_pauses", 0) for r in results),
        "confidence_drops": sum(r.get("confidence_drops", 0) for r in results),
        "filler_words": results[0].get("filler_words", []),
        "questions": [],
        "weaknesses": weaknesses[:5],
        "improvement_plan": plans[:4],
    }


# ──────────────────────────────────────────
# MAIN PIPELINE
# ──────────────────────────────────────────
def analyze_interview(
    transcript: str,
    word_list: list[str],
    duration_seconds: float,
    role: str, interview_type: str, round: str,
    format: str, tier: str, experience: str,
) -> dict:

    # Step 1 — Count filler words
    filler_counts = {}
    text_lower = transcript.lower()
    for fw in FILLER_WORDS:
        count = len(re.findall(r'\b' + re.escape(fw) + r'\b', text_lower))
        if count > 0:
            filler_counts[fw] = count

    filler_words_list = [{"word": w, "count": c} for w, c in sorted(filler_counts.items(), key=lambda x: -x[1])]
    total_fillers = sum(filler_counts.values())

    # Step 2 — WPM
    wpm = int(len(word_list) / (duration_seconds / 60)) if duration_seconds > 0 else 0

    # Step 3 — Full context
    context = f"""
Role: {role or 'Not specified'}
Interview type: {interview_type or 'General'}
Round: {round or 'Not specified'}
Format: {format or 'Not specified'}
Company tier: {tier or 'Not specified'}
Experience level: {experience or 'Not specified'}
Duration: {int(duration_seconds)}s | WPM: {wpm} | Total fillers: {total_fillers}

TRANSCRIPT:
{transcript}
""".strip()

    api_key = os.getenv("GROQ_API_KEY", "").strip()

    # Step 4 — AI Analysis
    if api_key:
        try:
            if len(word_list) > 150:
                # ── CHUNKED FLOW ──
                print(f"[CHUNKING] {len(word_list)} words — chunking activated")
                chunks = chunk_transcript_sentences(transcript)
                print(f"[CHUNKING] Total chunks: {len(chunks)}")

                all_results = []
                for i, chunk in enumerate(chunks):
                    chunk_context = f"""
Role: {role or 'Not specified'}
Interview type: {interview_type or 'General'}
SEGMENT {i+1} of {len(chunks)}:
{chunk}
""".strip()
                    try:
                        print(f"[CHUNK {i+1}] Analyzing {len(chunk.split())} words...")
                        res = _ai_analyze(chunk_context, filler_words_list, total_fillers)
                        if res:
                            all_results.append(res)
                    except Exception as e:
                        print(f"[WARNING] Chunk {i+1} failed: {e}")

                merged = merge_results(all_results)
                if merged:
                    try:
                        print("[QUESTIONS] Generating questions from full transcript...")
                        # ✅ FIX 1 — pass role here
                        merged["questions"] = _generate_questions(context, role)
                    except Exception as e:
                        print(f"[WARNING] Question generation failed: {e}")
                        merged["questions"] = []
                    return merged

            # ── SINGLE PASS FLOW ──
            print("[SINGLE PASS] Short transcript — direct analysis")
            return _ai_analyze_full(context, filler_words_list, total_fillers)

        except Exception as e:
            print(f"[WARNING] Groq failed: {e} — using local scoring")

    # Step 5 — Local fallback
    return compute_local_scores(
        transcript=transcript,
        word_list=word_list,
        duration_seconds=duration_seconds,
        filler_words_list=filler_words_list,
        total_fillers=total_fillers,
        wpm=wpm,
        role=role,
    )


# ──────────────────────────────────────────
# AI — PER CHUNK (no questions)
# ──────────────────────────────────────────
def _ai_analyze(context: str, filler_words_list: list, total_fillers: int) -> dict:
    prompt = f"""You are an expert interview coach analyzing ONE segment of an interview.

{context}

Return ONLY valid JSON (no markdown) with ONLY these fields:
{{
  "overall_score": <int 1-10>,
  "summary": "<2 honest sentences about THIS segment only>",
  "total_fillers": {total_fillers},
  "long_pauses": <int>,
  "confidence_drops": <int>,
  "filler_words": {json.dumps(filler_words_list)},
  "weaknesses": [
    {{"name": "<unique weakness>", "impact": "<high|medium|low>", "severity": <int 0-100>}}
  ],
  "improvement_plan": [
    {{"week": "Week 1-2", "goal": "<unique goal>", "tasks": ["<task1>", "<task2>", "<task3>"]}}
  ]
}}

RULES:
- Do NOT include questions field
- Focus ONLY on this segment
- Do NOT repeat generic answers"""

    result = _call_groq(prompt)
    result["questions"] = []
    return result


# ──────────────────────────────────────────
# AI — FULL TRANSCRIPT (with questions)
# ──────────────────────────────────────────
def _ai_analyze_full(context: str, filler_words_list: list, total_fillers: int) -> dict:
    prompt = f"""You are an expert interview coach analyzing a full interview transcript.

{context}

Return ONLY valid JSON (no markdown) with this exact structure:
{{
  "overall_score": <int 1-10>,
  "summary": "<2 honest sentences about performance>",
  "total_fillers": {total_fillers},
  "long_pauses": <int>,
  "confidence_drops": <int>,
  "filler_words": {json.dumps(filler_words_list)},
  "questions": [
    {{
      "number": 1,
      "question": "<actual interview question asked>",
      "clarity": <int 1-10>,
      "depth": <int 1-10>,
      "relevance": <int 1-10>,
      "feedback": "<specific critique of THIS answer only>",
      "timestamp": "<MM:SS>",
      "pause_detected": <true|false>
    }}
  ],
  "weaknesses": [
    {{"name": "<unique weakness>", "impact": "<high|medium|low>", "severity": <int 0-100>}}
  ],
  "improvement_plan": [
    {{"week": "Week 1-2", "goal": "<unique goal>", "tasks": ["<task1>", "<task2>", "<task3>"]}}
  ]
}}

RULES:
- Generate 3-5 UNIQUE questions from actual transcript
- Analyze each answer SEPARATELY
- Give DIFFERENT feedback for each answer
- 4-5 UNIQUE weaknesses
- 4 UNIQUE improvement weeks"""

    return _call_groq(prompt)


# ──────────────────────────────────────────
# AI — QUESTIONS ONLY (for chunked flow)
# ──────────────────────────────────────────
def _generate_questions(context: str, role: str) -> list:
    # ✅ FIX 2 — role added to prompt
    prompt = f"""You are an expert interview coach analyzing a full interview transcript.

Role applying for: {role or 'Not specified'}

{context}

Identify the actual interview questions asked and analyze each answer given by the candidate.

Return ONLY a valid JSON array (no markdown):
[
  {{
    "number": 1,
    "question": "<the QUESTION asked by the interviewer, NOT the candidate's answer>",
    "candidate_answer": "<summary of what the candidate said>",
    "clarity": <int 1-10>,
    "depth": <int 1-10>,
    "relevance": <int 1-10>,
    "feedback": "<specific critique of THIS answer only>",
    "timestamp": "<estimated MM:SS>",
    "pause_detected": <true|false>
  }}
]

RULES:
- Identify 3-5 REAL questions from the transcript
- Analyze each answer SEPARATELY
- Give DIFFERENT feedback for each answer
- DO NOT repeat same feedback
- Base everything on what candidate ACTUALLY said
- DO NOT generate generic questions"""

    raw = _call_groq_raw(prompt)
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    return json.loads(raw[start:end])


# ──────────────────────────────────────────
# GROQ CALLS
# ──────────────────────────────────────────
def _call_groq(prompt: str) -> dict:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No valid JSON found in Groq response")
    return json.loads(raw[start:end])


def _call_groq_raw(prompt: str) -> str:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    resp = client.chat.completions.create(
        # ✅ FIX 3 — updated model
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    raw = resp.choices[0].message.content.strip()
    return raw.replace("```json", "").replace("```", "").strip()