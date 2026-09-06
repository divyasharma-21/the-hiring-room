"""
The Hiring Room — FastAPI backend
AI-Powered Resume & Interview Coach (Girl Geeks 2026 · Case 01)
"""

from __future__ import annotations
import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from config import UPLOAD_DIR, GEMINI_API_KEY
from database import init_db, get_db, Session, Message, Evaluation, User
from resume_analyzer import extract_resume_text, analyze_resume
from demo_data import DEMO_CANDIDATE, DEMO_RESUME, DEMO_JD, DEMO_ANSWERS
from coding_round import pick_debug_problem, pick_coding_problem, review_debug, review_coding, generate_ai_problem
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_optional_user,
)
from ai_panel import (
    PERSONAS,
    generate_opening_question,
    generate_followup,
    detect_star,
    rewrite_answer,
    run_deliberation,
    enrich_resume_summary,
    recommend_resources,
    confidence_tip,
    improvement_bullets,
    detect_leadership_signals,
    mentor_note,
    _gemini_available,
)

app = FastAPI(
    title="The Hiring Room",
    description="Multi-persona AI panel for resume & interview evaluation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    if _gemini_available():
        from ai_panel import _call_gemini
        test = _call_gemini("Reply with exactly: OK", temperature=0)
        if test.strip().upper().startswith("OK"):
            print("[Hiring Room] Gemini connected — live AI questions/deliberation/coding review enabled.")
        else:
            print(
                "[Hiring Room] WARNING: GEMINI_API_KEY is set but the test call failed "
                "(see [Gemini error] above). Falling back to rule-based templates. "
                "Check your key and GEMINI_MODEL in backend/.env."
            )
    else:
        print(
            "[Hiring Room] No GEMINI_API_KEY set — running on rule-based templates only. "
            "Add a free key from https://aistudio.google.com/apikey to backend/.env to enable real AI."
        )


# ---------- Schemas ----------

class AnalyzeTextRequest(BaseModel):
    resume_text: str
    job_description: str
    candidate_name: str = ""
    language: Optional[str] = "en"  # en | hi | kn


class StartInterviewRequest(BaseModel):
    session_id: str
    language: Optional[str] = "en"
    role: Optional[str] = None  # target role label, e.g. "Data Analyst"


class QuickInterviewRequest(BaseModel):
    """Start a realistic panel interview without resume/JD analysis."""
    language: Optional[str] = "en"
    role: Optional[str] = "sde"  # sde | data | product | internship
    focus: Optional[str] = "panel"  # panel | hr | technical | behavioral
    candidate_name: Optional[str] = ""


class AnswerRequest(BaseModel):
    session_id: str
    answer: str
    next_persona: Optional[str] = None  # optional override
    confidence: Optional[int] = None  # 1-5 self rating
    language: Optional[str] = "en"


class DeliberateRequest(BaseModel):
    session_id: str
    language: Optional[str] = "en"


class RewriteRequest(BaseModel):
    session_id: str
    message_id: int
    language: Optional[str] = "en"


class CodingStartRequest(BaseModel):
    session_id: Optional[str] = None  # optional — creates a standalone coding/debug session
    mode: str = "debug"  # debug | code
    difficulty: Optional[str] = None  # easy | medium | hard | any/None
    exclude_ids: Optional[list] = None  # already used in this session
    language: Optional[str] = "python"  # programming language
    ui_language: Optional[str] = "en"  # UI / AI response language


class CodingSubmitRequest(BaseModel):
    session_id: str
    mode: str  # debug | code
    problem_id: str
    problem: Optional[dict] = None  # full problem snapshot (needed for AI-generated)
    submission: str
    language: Optional[str] = "en"  # UI language for AI feedback


# ---------- Helpers ----------

def _session_or_404(db: DBSession, session_id: str, user: Optional[User] = None) -> Session:
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(404, "Session not found")
    if user is not None and s.user_id and s.user_id != user.id:
        raise HTTPException(403, "Access denied")
    return s


def _user_public(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name or "",
        "preferred_language": u.preferred_language or "en",
        "target_role": u.target_role or "sde",
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _session_target_role(s: Session) -> str:
    """Recover target role stored on the session (analysis meta or JD stub)."""
    try:
        a = _analysis_dict(s)
        if isinstance(a, dict) and a.get("_target_role"):
            return str(a["_target_role"])
    except Exception:
        pass
    import re
    jd = s.job_description or ""
    m = re.search(r"hiring for a\s+(.+?)\s+role", jd, re.I)
    if m:
        return m.group(1).strip()
    return "professional"


def _analysis_dict(s: Session) -> dict:
    if not s.resume_analysis_json:
        return {}
    try:
        return json.loads(s.resume_analysis_json)
    except Exception:
        return {}


def _history(db: DBSession, session_id: str) -> list[dict]:
    rows = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id.asc())
        .all()
    )
    out = []
    for m in rows:
        out.append({
            "id": m.id,
            "role": m.role,
            "persona": m.persona,
            "content": m.content,
            "star": json.loads(m.star_json) if m.star_json else None,
            "rewritten": m.rewritten,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return out


# ---------- Routes ----------


class DemoStartRequest(BaseModel):
    language: Optional[str] = "en"


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    preferred_language: Optional[str] = None
    target_role: Optional[str] = None


# ---------- Auth ----------


@app.post("/api/auth/register")
def register(body: RegisterRequest, db: DBSession = Depends(get_db)):
    email = (body.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email is required")
    if not body.password or len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "An account with this email already exists")
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=email,
        password_hash=hash_password(body.password),
        full_name=(body.full_name or "").strip() or email.split("@")[0],
    )
    db.add(user)
    db.commit()
    token = create_access_token(uid, email)
    return {"token": token, "user": _user_public(user)}


@app.post("/api/auth/login")
def login(body: LoginRequest, db: DBSession = Depends(get_db)):
    email = (body.email or "").strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    user.last_login = datetime.utcnow()
    db.commit()
    token = create_access_token(user.id, user.email)
    return {"token": token, "user": _user_public(user)}


@app.get("/api/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    return {"user": _user_public(user)}


@app.patch("/api/auth/profile")
def update_profile(body: ProfileUpdateRequest, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.preferred_language is not None:
        user.preferred_language = body.preferred_language
    if body.target_role is not None:
        user.target_role = body.target_role
    db.commit()
    return {"user": _user_public(user)}


@app.get("/api/dashboard")
def dashboard(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    sessions = (
        db.query(Session)
        .filter(Session.user_id == user.id)
        .order_by(Session.created_at.desc())
        .all()
    )
    completed = [s for s in sessions if s.status == "complete"]
    with_analysis = [s for s in sessions if s.resume_analysis_json]
    resume_scores = []
    interview_scores = []
    for s in sessions:
        if s.resume_analysis_json:
            try:
                a = json.loads(s.resume_analysis_json)
                if isinstance(a.get("overall_score"), (int, float)):
                    resume_scores.append(a["overall_score"])
            except Exception:
                pass
        if s.consensus_score is not None:
            interview_scores.append(s.consensus_score)
    recent = []
    for s in sessions[:8]:
        recent.append({
            "session_id": s.id,
            "candidate_name": s.candidate_name,
            "status": s.status,
            "session_type": s.session_type or "full",
            "consensus_score": s.consensus_score,
            "consensus_verdict": s.consensus_verdict,
            "star_avg": s.star_avg,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "has_analysis": bool(s.resume_analysis_json),
        })
    strengths, gaps = [], []
    if with_analysis:
        try:
            a = json.loads(with_analysis[0].resume_analysis_json)
            strengths = (a.get("matching_skills") or [])[:6]
            gaps = (a.get("missing_skills") or [])[:6]
        except Exception:
            pass
    return {
        "user": _user_public(user),
        "stats": {
            "sessions_total": len(sessions),
            "interviews_completed": len(completed),
            "resume_analyses": len(with_analysis),
            "avg_resume_score": round(sum(resume_scores) / len(resume_scores), 1) if resume_scores else None,
            "avg_interview_score": round(sum(interview_scores) / len(interview_scores), 1) if interview_scores else None,
            "latest_resume_score": resume_scores[0] if resume_scores else None,
            "latest_interview_score": interview_scores[0] if interview_scores else None,
        },
        "recent": recent,
        "strengths": strengths,
        "gaps": gaps,
    }


@app.get("/api/history")
def history(
    type: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    q = db.query(Session).filter(Session.user_id == user.id).order_by(Session.created_at.desc())
    rows = q.limit(100).all()
    out = []
    for s in rows:
        score = s.consensus_score
        st = (s.session_type or "full").lower()
        if st == "coding":
            activity = "Coding round"
        elif st == "debug":
            activity = "Debug round"
        elif s.status in ("interviewing", "deliberating", "complete") or st in ("panel", "behavioral", "technical", "hr"):
            activity = "Interview"
        else:
            activity = "Resume analysis"
        if type == "interviews" and activity != "Interview":
            continue
        if type == "resume" and activity != "Resume analysis":
            continue
        if type == "coding" and activity != "Coding round":
            continue
        if type == "debug" and activity != "Debug round":
            continue
        out.append({
            "session_id": s.id,
            "activity": activity,
            "session_type": s.session_type or "full",
            "status": s.status,
            "score": score,
            "star_avg": s.star_avg,
            "verdict": s.consensus_verdict,
            "candidate_name": s.candidate_name,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return {"items": out}


@app.post("/api/demo/start")
def demo_start(
    body: Optional[DemoStartRequest] = None,
    db: DBSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """One-click demo session with sample resume + JD analysis."""
    analysis = analyze_resume(DEMO_RESUME, DEMO_JD, language="en")
    try:
        analysis["summary"] = enrich_resume_summary(analysis, DEMO_RESUME, DEMO_JD, language="en") or analysis["summary"]
    except Exception:
        pass
    resources = recommend_resources(analysis=analysis, language="en")
    sid = str(uuid.uuid4())
    s = Session(
        id=sid,
        user_id=user.id if user else None,
        candidate_name=DEMO_CANDIDATE,
        resume_text=DEMO_RESUME,
        job_description=DEMO_JD,
        resume_analysis_json=json.dumps(analysis),
        status="ready",
        session_type="full",
    )
    db.add(s)
    db.commit()
    return {
        "session_id": sid,
        "candidate_name": DEMO_CANDIDATE,
        "analysis": analysis,
        "resources": resources,
        "status": s.status,
        "demo": True,
        "sample_answers": DEMO_ANSWERS,
        "resume_text": DEMO_RESUME,
        "job_description": DEMO_JD,
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "gemini": _gemini_available(),
        "personas": list(PERSONAS.keys()),
        "time": datetime.utcnow().isoformat(),
    }


@app.post("/api/analyze")
async def analyze_upload(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    candidate_name: str = Form(""),
    language: str = Form("en"),
    db: DBSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    raw = await resume.read()
    if not raw:
        raise HTTPException(400, "Empty resume file")
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(400, "Resume too large (max 8MB)")

    text = extract_resume_text(resume.filename or "resume.pdf", raw)
    if not text.strip():
        raise HTTPException(400, "Could not extract text from resume. Try PDF/DOCX with selectable text.")

    # persist file
    sid = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{sid}_{resume.filename}"
    dest.write_bytes(raw)

    analysis = analyze_resume(text, job_description, language=(language or "en").lower())
    try:
        analysis["summary"] = enrich_resume_summary(analysis, text, job_description, language=(language or "en").lower()) or analysis["summary"]
    except Exception:
        pass

    resources = recommend_resources(analysis=analysis, language=(language or "en").lower())

    s = Session(
        id=sid,
        user_id=user.id if user else None,
        candidate_name=candidate_name or (user.full_name if user else "Candidate"),
        resume_text=text,
        job_description=job_description,
        resume_analysis_json=json.dumps(analysis),
        status="ready",
        session_type="full",
    )
    db.add(s)
    db.commit()

    return {
        "session_id": sid,
        "candidate_name": s.candidate_name,
        "analysis": analysis,
        "resources": resources,
        "status": s.status,
    }


@app.post("/api/analyze/text")
def analyze_text(body: AnalyzeTextRequest, db: DBSession = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    if not body.resume_text.strip() or not body.job_description.strip():
        raise HTTPException(400, "resume_text and job_description are required")

    language = (getattr(body, "language", None) or "en").lower()
    analysis = analyze_resume(body.resume_text, body.job_description, language=language)
    try:
        analysis["summary"] = enrich_resume_summary(analysis, body.resume_text, body.job_description, language=language) or analysis["summary"]
    except Exception:
        pass

    resources = recommend_resources(analysis=analysis, language=language)

    sid = str(uuid.uuid4())
    s = Session(
        id=sid,
        user_id=user.id if user else None,
        candidate_name=body.candidate_name or (user.full_name if user else "Candidate"),
        resume_text=body.resume_text,
        job_description=body.job_description,
        resume_analysis_json=json.dumps(analysis),
        status="ready",
        session_type="full",
    )
    db.add(s)
    db.commit()

    return {
        "session_id": sid,
        "candidate_name": s.candidate_name,
        "analysis": analysis,
        "resources": resources,
        "status": s.status,
    }


@app.get("/api/session/{session_id}")
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    s = _session_or_404(db, session_id)
    return {
        "session_id": s.id,
        "candidate_name": s.candidate_name,
        "status": s.status,
        "analysis": _analysis_dict(s),
        "history": _history(db, session_id),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }



@app.post("/api/interview/quick-start")
def quick_start_interview(
    body: QuickInterviewRequest,
    db: DBSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Pure interview practice — no resume or JD required. Realistic general panel questions."""
    lang = (body.language or "en").lower()
    role = body.role or "sde"
    focus = (body.focus or "panel").lower()
    name = (body.candidate_name or "").strip()
    if user and not name:
        name = user.full_name or user.email.split("@")[0]
    if not name:
        name = "Candidate"

    # Lightweight generic context so AI/fallbacks still produce solid questions
    resume_stub = (
        f"Candidate: {name}. Target role: {role}. "
        "Early-to-mid career software professional practicing for interviews. "
        "Has worked on academic and personal projects involving programming, teamwork, and problem-solving."
    )
    role_jd_hints = {
        "sde": "Software engineering: coding, APIs, debugging, system design basics, code quality.",
        "data": "Data Analyst: SQL, data cleaning, dashboards, statistics, stakeholder insights.",
        "data analyst": "Data Analyst: SQL, Python/pandas, visualization, metrics, business insights.",
        "data scientist": "Data Science: ML basics, experimentation, statistics, Python, model evaluation.",
        "product": "Product: prioritization, user problems, metrics, roadmaps, stakeholder alignment.",
        "internship": "Internship: learning agility, fundamentals, teamwork, communication.",
        "backend": "Backend: APIs, databases, reliability, performance, system design.",
        "frontend": "Frontend: UI, accessibility, state management, performance.",
        "fullstack": "Full-stack: end-to-end features, APIs + UI, ownership of delivery.",
        "ml engineer": "ML engineering: training pipelines, evaluation, deployment, data quality.",
        "business analyst": "Business analysis: requirements, process, stakeholders, data-informed decisions.",
    }
    role_key = (role or "sde").lower().strip()
    hint = role_jd_hints.get(role_key)
    if not hint:
        for k, v in role_jd_hints.items():
            if k in role_key or role_key in k:
                hint = v
                break
    if not hint:
        hint = f"Role-specific skills and impact for a {role} position."
    jd_stub = (
        f"We are hiring for a {role} role. {hint} "
        "Looking for clear communication, ownership, problem-solving ability, "
        "and the capacity to learn quickly. Behavioral and technical depth both matter for this role."
    )
    if focus in ("hr", "behavioral"):
        persona = "hr"
        session_type = "behavioral"  # HR-only
    elif focus in ("technical", "tech", "tech_lead"):
        persona = "tech_lead"
        session_type = "technical"  # Tech Lead-only
    elif focus in ("hiring_manager", "hm"):
        persona = "hiring_manager"
        session_type = "hiring_manager"  # HM-only
    else:
        persona = "hr"
        session_type = "panel"

    sid = str(uuid.uuid4())
    s = Session(
        id=sid,
        user_id=user.id if user else None,
        candidate_name=name,
        resume_text=resume_stub,
        job_description=jd_stub,
        resume_analysis_json=json.dumps({"_target_role": role}),
        status="interviewing",
        session_type=session_type,
    )
    db.add(s)
    db.flush()

    q = generate_opening_question(persona, resume_stub, jd_stub, analysis=None, role=role, language=lang)
    msg = Message(session_id=s.id, role=persona, persona=persona, content=q)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {
        "session_id": s.id,
        "status": s.status,
        "session_type": session_type,
        "candidate_name": name,
        "quick": True,
        "message": {
            "id": msg.id,
            "role": msg.role,
            "persona": msg.persona,
            "content": msg.content,
            "persona_meta": PERSONAS.get(persona, {}),
        },
        "history": _history(db, s.id),
    }


@app.post("/api/interview/start")
def start_interview(body: StartInterviewRequest, db: DBSession = Depends(get_db)):
    s = _session_or_404(db, body.session_id)
    if s.status not in ("ready", "interviewing", "complete"):
        # allow restart-ish
        pass

    # clear prior messages if restarting
    db.query(Message).filter(Message.session_id == s.id).delete()
    db.query(Evaluation).filter(Evaluation.session_id == s.id).delete()

    analysis = _analysis_dict(s)
    lang = getattr(body, "language", None) or "en"
    if body.role:
        analysis = dict(analysis or {})
        analysis["_target_role"] = body.role
        s.resume_analysis_json = json.dumps(analysis)
    role = body.role or _session_target_role(s)
    stype = (s.session_type or "full").lower()
    if stype in ("technical", "tech", "tech_lead"):
        open_persona = "tech_lead"
    elif stype in ("hiring_manager", "hm"):
        open_persona = "hiring_manager"
    elif stype in ("behavioral", "hr"):
        open_persona = "hr"
    else:
        open_persona = "hr"
    q = generate_opening_question(
        open_persona, s.resume_text, s.job_description, analysis, role=role, language=lang
    )
    msg = Message(
        session_id=s.id,
        role=open_persona,
        persona=open_persona,
        content=q,
    )
    db.add(msg)
    s.status = "interviewing"
    db.commit()
    db.refresh(msg)

    return {
        "session_id": s.id,
        "status": s.status,
        "message": {
            "id": msg.id,
            "role": msg.role,
            "persona": msg.persona,
            "content": msg.content,
            "persona_meta": PERSONAS["hr"],
        },
        "history": _history(db, s.id),
    }


@app.post("/api/interview/answer")
async def submit_answer(body: AnswerRequest, db: DBSession = Depends(get_db)):
    s = _session_or_404(db, body.session_id)
    if s.status not in ("interviewing", "ready"):
        raise HTTPException(400, f"Session status is {s.status}")

    answer = (body.answer or "").strip()
    if not answer:
        raise HTTPException(400, "Answer cannot be empty")

    # Find preceding panel question (unchanged)
    last_panel_msg = (
        db.query(Message)
        .filter(Message.session_id == s.id, Message.role.in_(list(PERSONAS.keys())))
        .order_by(Message.id.desc())
        .first()
    )
    asked_question = last_panel_msg.content if last_panel_msg else ""
    asked_persona = last_panel_msg.persona if last_panel_msg and last_panel_msg.persona in PERSONAS else "hr"

    # Determine candidate history & fair turn rotation (unchanged)
    history = _history(db, s.id)
    interviewer_msgs = [m for m in history if m["role"] in PERSONAS]
    order = ["hr", "tech_lead", "hiring_manager"]
    counts = {p: 0 for p in order}
    for m in interviewer_msgs:
        p = m.get("persona") or m.get("role")
        if p in counts:
            counts[p] += 1

    turn = len(interviewer_msgs)

    # Focused modes: stay on a single persona for realistic HR-only or Tech-only panels
    stype = (s.session_type or "panel").lower()
    if stype in ("behavioral", "hr"):
        next_p = "hr"
    elif stype in ("technical", "tech", "tech_lead"):
        next_p = "tech_lead"
    elif stype in ("hiring_manager", "hm"):
        next_p = "hiring_manager"
    elif body.next_persona and body.next_persona in PERSONAS:
        next_p = body.next_persona
    else:
        min_count = min(counts.values()) if counts else 0
        candidates = [p for p in order if counts[p] == min_count]
        next_p = candidates[0]

    lang = getattr(body, "language", None) or "en"
    # --- PERFORMANCE FIX: Run all 3 independent Gemini calls concurrently ---
    star_task = asyncio.to_thread(detect_star, answer, lang)
    rewrite_task = asyncio.to_thread(
        rewrite_answer,
        answer,
        "",
        None,
        asked_question,
        asked_persona,
        s.resume_text,
        s.job_description,
        lang,
    )
    followup_task = asyncio.to_thread(
        generate_followup,
        next_p,
        history,
        s.resume_text,
        s.job_description,
        lang,
        _session_target_role(s),
    )

    # Wait for all 3 tasks to finish in parallel
    star, rewrite_result, follow = await asyncio.gather(star_task, rewrite_task, followup_task)

    # Attach STAR metadata (unchanged)
    rewritten = rewrite_result["text"]
    tip = confidence_tip(answer, star, body.confidence, language=lang)
    improved = improvement_bullets(answer, rewritten, star, language=lang)
    leadership = detect_leadership_signals(answer, language=lang)
    star = {
        **star,
        "confidence": body.confidence,
        "confidence_tip": tip,
        "improvements": improved,
        "leadership": leadership,
        "rewrite_mode": rewrite_result["mode"],
    }

    # Save Candidate Answer (unchanged)
    cand = Message(
        session_id=s.id,
        role="candidate",
        persona=None,
        content=answer,
        star_json=json.dumps(star),
        rewritten=rewritten,
    )
    db.add(cand)

    # Save Panel Question (unchanged)
    imsg = Message(
        session_id=s.id,
        role=next_p,
        persona=next_p,
        content=follow,
    )
    db.add(imsg)
    db.commit()

    cand_turns = sum(1 for m in history if m["role"] == "candidate") + 1

    # Exact same response schema expected by frontend
    return {
        "session_id": s.id,
        "candidate_message": {
            "id": cand.id,
            "role": "candidate",
            "content": answer,
            "star": star,
            "rewritten": rewritten,
            "confidence": body.confidence,
            "confidence_tip": tip,
            "improvements": improved,
        },
        "panel_message": {
            "id": imsg.id,
            "role": imsg.role,
            "persona": imsg.persona,
            "content": imsg.content,
            "persona_meta": PERSONAS.get(next_p, {}),
        },
        "history": _history(db, s.id),
        "turns": turn + 1,
        "can_deliberate": cand_turns >= 1,
        "persona_counts": counts,
    }


@app.post("/api/interview/deliberate")
def deliberate(body: DeliberateRequest, db: DBSession = Depends(get_db)):
    s = _session_or_404(db, body.session_id)
    history = _history(db, s.id)
    cand_count = sum(1 for m in history if m["role"] == "candidate")
    if cand_count < 1:
        raise HTTPException(400, "Need at least one candidate answer before deliberation")

    s.status = "deliberating"
    db.commit()

    analysis = _analysis_dict(s)
    lang = getattr(body, "language", None) or "en"
    result = run_deliberation(history, s.resume_text, s.job_description, analysis, language=lang, focus=(s.session_type or "panel"))

    # persist evaluations
    db.query(Evaluation).filter(Evaluation.session_id == s.id).delete()
    individual = result.get("individual") or {}
    for persona, data in individual.items():
        ev = Evaluation(
            session_id=s.id,
            persona=persona,
            score=data.get("score"),
            feedback=json.dumps(data),
            strengths=json.dumps(data.get("strengths") or []),
            concerns=json.dumps(data.get("concerns") or []),
        )
        db.add(ev)
    consensus = result.get("consensus") or {}
    evc = Evaluation(
        session_id=s.id,
        persona="consensus",
        score=consensus.get("score"),
        feedback=json.dumps(consensus),
        strengths=json.dumps([]),
        concerns=json.dumps([]),
    )
    db.add(evc)

    s.status = "complete"
    cons = result.get("consensus") or {}
    if isinstance(cons.get("score"), (int, float)):
        s.consensus_score = float(cons["score"])
    if cons.get("verdict"):
        s.consensus_verdict = str(cons["verdict"])
    db.commit()

    star_history = [m.get("star") for m in history if m.get("role") == "candidate" and m.get("star")]
    resources = recommend_resources(
        analysis=analysis,
        star_history=star_history,
        deliberation=result,
        language=lang,
    )
    scores = []
    for st in star_history:
        if isinstance(st, dict) and isinstance(st.get("score"), (int, float)):
            scores.append(st["score"])
    star_avg = round(sum(scores) / len(scores), 1) if scores else None
    if star_avg is not None:
        s.star_avg = star_avg
        db.commit()
    note = mentor_note(analysis, result, star_avg, language=lang)

    return {
        "session_id": s.id,
        "status": s.status,
        "deliberation": result,
        "history": history,
        "analysis": analysis,
        "resources": resources,
        "mentor_note": note,
        "star_avg": star_avg,
    }


@app.post("/api/rewrite")
def rewrite_one(body: RewriteRequest, db: DBSession = Depends(get_db)):
    s = _session_or_404(db, body.session_id)
    msg = db.query(Message).filter(Message.id == body.message_id, Message.session_id == s.id).first()
    if not msg or msg.role != "candidate":
        raise HTTPException(404, "Candidate message not found")

    prev_panel_msg = (
        db.query(Message)
        .filter(Message.session_id == s.id, Message.id < msg.id, Message.role.in_(list(PERSONAS.keys())))
        .order_by(Message.id.desc())
        .first()
    )
    asked_question = prev_panel_msg.content if prev_panel_msg else ""
    asked_persona = prev_panel_msg.persona if prev_panel_msg and prev_panel_msg.persona in PERSONAS else "hr"

    star = detect_star(msg.content, language=getattr(body, "language", None) or "en")
    rewrite_result = rewrite_answer(
        msg.content, star=star, question=asked_question, persona=asked_persona,
        resume_text=s.resume_text, jd_text=s.job_description,
    )
    rewritten = rewrite_result["text"]
    star = {**star, "rewrite_mode": rewrite_result["mode"]}
    msg.rewritten = rewritten
    msg.star_json = json.dumps(star)
    db.commit()
    return {
        "message_id": msg.id,
        "original": msg.content,
        "rewritten": rewritten,
        "rewrite_mode": rewrite_result["mode"],
        "star": star,
    }





@app.get("/api/resume/latest")
def latest_resume(
    db: DBSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Most recent session that has a real resume + JD analysis for this user."""
    rows = (
        db.query(Session)
        .filter(Session.user_id == user.id)
        .order_by(Session.created_at.desc())
        .limit(40)
        .all()
    )
    for s in rows:
        analysis = _analysis_dict(s)
        has_resume = bool((s.resume_text or "").strip()) and len((s.resume_text or "").strip()) > 80
        has_jd = bool((s.job_description or "").strip()) and "We are hiring for a" not in (s.job_description or "")[:40]
        # Prefer sessions that actually ran analysis
        if has_resume and has_jd and analysis and analysis.get("overall_score") is not None:
            return {
                "session_id": s.id,
                "candidate_name": s.candidate_name,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "overall_score": analysis.get("overall_score"),
                "matching_skills": (analysis.get("matching_skills") or [])[:8],
                "missing_skills": (analysis.get("missing_skills") or [])[:8],
                "has_analysis": True,
            }
    return {"has_analysis": False}


@app.post("/api/interview/from-latest")
def interview_from_latest(
    body: QuickInterviewRequest,
    db: DBSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a focused/panel interview using the user's most recent resume+JD analysis."""
    latest = latest_resume(db=db, user=user)
    if not latest.get("has_analysis"):
        raise HTTPException(400, "No saved resume+JD analysis found. Upload and analyze first.")

    src = _session_or_404(db, latest["session_id"], user)
    analysis = _analysis_dict(src)
    lang = (body.language or "en").lower()
    focus = (body.focus or "panel").lower()
    name = (body.candidate_name or src.candidate_name or user.full_name or "Candidate").strip()

    if focus in ("hr", "behavioral"):
        persona, session_type = "hr", "behavioral"
    elif focus in ("technical", "tech", "tech_lead"):
        persona, session_type = "tech_lead", "technical"
    elif focus in ("hiring_manager", "hm"):
        persona, session_type = "hiring_manager", "hiring_manager"
    else:
        persona, session_type = "hr", "panel"

    sid = str(uuid.uuid4())
    meta = dict(analysis or {})
    meta["_target_role"] = body.role or meta.get("_target_role") or "sde"
    s = Session(
        id=sid,
        user_id=user.id,
        candidate_name=name,
        resume_text=src.resume_text,
        job_description=src.job_description,
        resume_analysis_json=json.dumps(meta),
        status="interviewing",
        session_type=session_type,
    )
    db.add(s)
    db.flush()
    q = generate_opening_question(
        persona, s.resume_text, s.job_description, analysis=analysis, role=body.role or "sde", language=lang
    )
    msg = Message(session_id=s.id, role=persona, persona=persona, content=q)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {
        "session_id": s.id,
        "session_type": session_type,
        "candidate_name": name,
        "history": [{
            "id": msg.id, "role": msg.role, "persona": msg.persona, "content": msg.content,
            "star": None, "mentor_tip": None,
        }],
        "analysis": analysis,
        "from_latest": True,
    }




@app.delete("/api/history/clear")
def clear_history(
    db: DBSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete all sessions (and cascaded messages/evaluations) for the current user."""
    rows = db.query(Session).filter(Session.user_id == user.id).all()
    n = len(rows)
    for s in rows:
        db.delete(s)
    db.commit()
    return {"ok": True, "deleted_sessions": n}




class RelocalizeRequest(BaseModel):
    session_id: str
    language: Optional[str] = "en"


@app.post("/api/session/relocalize")
def relocalize_session(
    body: RelocalizeRequest,
    db: DBSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Re-render analysis, deliberation, mentor note, and resources in a new UI language
    without changing scores or re-asking interview questions."""
    s = _session_or_404(db, body.session_id, user)
    lang = (body.language or "en").lower()
    if lang not in ("en", "hi", "kn"):
        lang = "en"

    history = _history(db, s.id)
    analysis = _analysis_dict(s)
    resources = []
    deliberation = None
    mentor = ""
    star_avg = s.star_avg

    # Recompute localized analysis text from same resume+JD (keeps scores/skills)
    if (s.resume_text or "").strip() and (s.job_description or "").strip():
        fresh = analyze_resume(s.resume_text, s.job_description, language=lang)
        # Preserve skill lists/scores from stored analysis if present (stable), refresh text fields
        if analysis:
            analysis["summary"] = fresh.get("summary") or analysis.get("summary")
            analysis["areas_to_improve"] = fresh.get("areas_to_improve") or analysis.get("areas_to_improve")
            analysis["ats_flags"] = fresh.get("ats_flags") or analysis.get("ats_flags")
            # keep matching/missing/gaps structure; localize gap status is UI-side
            if not analysis.get("gaps"):
                analysis["gaps"] = fresh.get("gaps") or []
            if analysis.get("overall_score") is None:
                analysis["overall_score"] = fresh.get("overall_score")
        else:
            analysis = fresh
        try:
            analysis["summary"] = enrich_resume_summary(
                analysis, s.resume_text, s.job_description, language=lang
            ) or analysis.get("summary")
        except Exception:
            pass
        # Translate per-requirement lines into UI language (JD text is often English)
        if lang in ("hi", "kn") and analysis.get("gaps"):
            try:
                from ai_panel import _call_gemini, _gemini_available
                if _gemini_available():
                    reqs = [g.get("requirement", "") for g in analysis["gaps"][:10]]
                    lang_name = {"hi": "Hindi", "kn": "Kannada"}.get(lang, "English")
                    raw = _call_gemini(
                        "Translate each line to " + lang_name + ". Return JSON array of strings, same order.\n"
                        + json.dumps(reqs, ensure_ascii=False),
                        system="Return only a JSON array of translated strings. No markdown.",
                        temperature=0.2,
                        language=lang,
                    )
                    from ai_panel import _parse_json_loose
                    arr = _parse_json_loose(raw)
                    if isinstance(arr, list):
                        for i, g in enumerate(analysis["gaps"][:len(arr)]):
                            if isinstance(arr[i], str) and arr[i].strip():
                                g["requirement"] = arr[i].strip()
            except Exception:
                pass
        # persist refreshed analysis text
        meta = dict(analysis)
        if analysis.get("_target_role"):
            meta["_target_role"] = analysis["_target_role"]
        s.resume_analysis_json = json.dumps(meta)

    # Re-run deliberation in new language if there are candidate answers
    cand_count = sum(1 for m in history if m.get("role") == "candidate")
    if cand_count >= 1:
        deliberation = run_deliberation(
            history, s.resume_text or "", s.job_description or "", analysis,
            language=lang, focus=(s.session_type or "panel"),
        )
        # Update stored evaluations text/scores for this language pass
        db.query(Evaluation).filter(Evaluation.session_id == s.id).delete()
        individual = (deliberation or {}).get("individual") or {}
        for persona, data in individual.items():
            db.add(Evaluation(
                session_id=s.id,
                persona=persona,
                score=data.get("score"),
                feedback=json.dumps(data),
                strengths=json.dumps(data.get("strengths") or []),
                concerns=json.dumps(data.get("concerns") or []),
            ))
        cons = (deliberation or {}).get("consensus") or {}
        db.add(Evaluation(
            session_id=s.id,
            persona="consensus",
            score=cons.get("score"),
            feedback=json.dumps(cons),
            strengths=json.dumps([]),
            concerns=json.dumps([]),
        ))
        if isinstance(cons.get("score"), (int, float)):
            s.consensus_score = float(cons["score"])
        if cons.get("verdict"):
            s.consensus_verdict = str(cons["verdict"])

        star_history = [m.get("star") for m in history if m.get("role") == "candidate" and m.get("star")]
        resources = recommend_resources(
            analysis=analysis, star_history=star_history, deliberation=deliberation, language=lang,
        )
        scores = [st["score"] for st in star_history if isinstance(st, dict) and isinstance(st.get("score"), (int, float))]
        star_avg = round(sum(scores) / len(scores), 1) if scores else s.star_avg
        if star_avg is not None:
            s.star_avg = star_avg
        mentor = mentor_note(analysis, deliberation, star_avg, language=lang)
    else:
        resources = recommend_resources(analysis=analysis, language=lang)

    db.commit()
    return {
        "session_id": s.id,
        "language": lang,
        "analysis": analysis,
        "deliberation": deliberation,
        "resources": resources,
        "mentor_note": mentor,
        "star_avg": star_avg,
        "history": history,
        "status": s.status,
    }


@app.post("/api/coding/start")
def coding_start(
    body: CodingStartRequest,
    db: DBSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    mode = (body.mode or "debug").lower()
    if mode not in ("debug", "code"):
        raise HTTPException(400, "mode must be debug or code")

    if body.session_id:
        s = _session_or_404(db, body.session_id, user)
    else:
        sid = str(uuid.uuid4())
        s = Session(
            id=sid,
            user_id=user.id if user else None,
            candidate_name=(user.full_name if user else "Candidate") or "Candidate",
            resume_text="",
            job_description="",
            resume_analysis_json="",
            status="ready",
            session_type="debug" if mode == "debug" else "coding",
        )
        db.add(s)
        db.commit()
    analysis = _analysis_dict(s)
    # Keep type accurate when starting from an existing resume session
    if mode == "debug":
        s.session_type = s.session_type if s.session_type in ("debug", "coding") else "debug"
    else:
        s.session_type = s.session_type if s.session_type in ("debug", "coding") else "coding"
    db.commit()
    difficulty = (body.difficulty or "").lower().strip() or None
    if difficulty in ("any", "all", ""):
        difficulty = None
    if difficulty and difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(400, "difficulty must be easy, medium, hard, or omitted")
    exclude = [x for x in (body.exclude_ids or []) if x]

    language = (body.language or "python").lower().strip()
    if language not in ("python", "javascript", "java", "cpp"):
        language = "python"

    ui_lang = (body.ui_language or "en").lower()
    problem = generate_ai_problem(
        mode=mode,
        difficulty=difficulty or "easy",
        language=language,
        ui_language=ui_lang,
        analysis=analysis,
        exclude_ids=exclude,
    )

    if not problem:
        raise HTTPException(
            404,
            "No more problems available for this mode/difficulty in this session. "
            "Try another difficulty or restart the session.",
        )

    return {
        "session_id": s.id,
        "mode": mode,
        "difficulty_filter": difficulty,
        "excluded": exclude,
        "problem": {
            "id": problem.get("id"),
            "title": problem.get("title"),
            "difficulty": problem.get("difficulty"),
            "language": problem.get("language", "python"),
            "prompt": problem.get("prompt"),
            "buggy_code": problem.get("buggy_code"),
            "starter": problem.get("starter"),
            "hint": problem.get("hint"),
            "topics": problem.get("topics") or [],
        },
    }


@app.post("/api/coding/submit")
def coding_submit(body: CodingSubmitRequest, db: DBSession = Depends(get_db)):
    s = _session_or_404(db, body.session_id)
    analysis = _analysis_dict(s)
    mode = (body.mode or "debug").lower()
    # re-pick banks and find problem by id
    from coding_round import DEBUG_PROBLEMS, CODING_PROBLEMS
    bank = DEBUG_PROBLEMS if mode == "debug" else CODING_PROBLEMS
    problem = next((dict(p) for p in bank if p.get("id") == body.problem_id), None)
    if not problem and isinstance(body.problem, dict) and body.problem.get("title"):
        problem = dict(body.problem)
    if not problem:
        problem = pick_debug_problem(analysis) if mode == "debug" else pick_coding_problem(analysis)

    if mode == "debug":
        lang = getattr(body, "language", None) or "en"
        result = review_debug(problem, body.submission, language=lang)
    else:
        lang = getattr(body, "language", None) or "en"
        result = review_coding(problem, body.submission, language=lang)

    # Persist score for history / dashboard
    try:
        sc = result.get("score")
        if isinstance(sc, (int, float)):
            s.consensus_score = float(sc)
            s.consensus_verdict = result.get("verdict") or s.consensus_verdict
            s.status = "complete"
            s.session_type = "debug" if mode == "debug" else "coding"
            db.commit()
    except Exception:
        pass

    return {
        "session_id": s.id,
        "mode": mode,
        "problem_id": problem.get("id"),
        "review": result,
        "persona": "tech_lead",
        "persona_meta": PERSONAS.get("tech_lead", {}),
    }


@app.get("/")
def root():

    return {
        "name": "The Hiring Room API",
        "docs": "/docs",
        "health": "/api/health",
    }
