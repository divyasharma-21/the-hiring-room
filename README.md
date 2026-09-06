# The Hiring Room

**AI-Powered Resume & Interview Coach**  
Girl Geeks 2026 · Case 01 · Ramaiah Institute of Technology

> *Not a score. A panel's reasoning.*

A national-level innovation project that replaces single opaque AI scores with a **three-persona hiring panel** (HR · Tech Lead · Hiring Manager). The panel interviews you, remembers your earlier answers, debates visibly (including real disagreements), and then delivers a reasoned verdict — plus STAR structure labels and a “Better You” rewrite that keeps *your* voice.

---

## Features

| Capability | What it does |
|---|---|
| **JD-Matched Resume Analysis** | Semantic match score, matching / missing skills, per-requirement gaps, ATS risk flags |
| **Three-Persona Panel** | HR (culture & communication), Tech Lead (depth & failure modes), Hiring Manager (impact & ownership) |
| **Interviewer Memory** | Follow-up questions that call back to things you said earlier |
| **Visible Deliberation** | Live debate transcript with genuine disagreement, then consensus |
| **STAR Detection** | Labels Situation / Task / Action / Result on every answer |
| **“Same Answer, Better You”** | Side-by-side rewrite that preserves your voice and facts |
| **Voice input** | Browser Web Speech API (Chrome / Edge) |
| **Demo Mode** | One-click sample resume + JD for reliable live demos |
| **STAR Progress** | Visual scores across answers during the interview |
| **Panel still wants** | 3 follow-up questions after deliberation |
| **PDF / Print report** | Download feedback via browser print |
| **Role selector** | SDE / Data / Product / Internship focus |
| **Answer timer** | Soft session timer during the interview |
| **Multilingual UI** | English · Hindi · Kannada — language selector in header, persisted via localStorage |
| **Language-aware AI** | Panel questions, rewrites, deliberation & coding feedback generated in the selected language |

Works **with or without** a Gemini API key. Without a key it falls back to high-quality offline simulation so the demo never breaks.

### Languages

Use the **language dropdown** in the top bar. Selection is saved in `localStorage` and restored on next visit.

- **English** (default)
- **Hindi** (हिन्दी)
- **Kannada** (ಕನ್ನಡ)

UI strings live in `frontend/src/i18n/translations.js`. AI responses receive the selected language so Gemini answers fully in that language when a key is configured.

---

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv          # optional but recommended
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Optional — for real Gemini-powered questions & deliberation
cp .env.example .env
# Edit .env and paste your free key from https://aistudio.google.com/apikey

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://127.0.0.1:8000/docs  
Health:  http://127.0.0.1:8000/api/health

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173  
(Vite proxies `/api` → backend on port 8000)

---

## Typical Demo Flow

1. **Home** → enter name (optional), upload PDF/DOCX resume *or* paste text, paste a full job description → **Analyze**.
2. **Analysis screen** → match score, matching/missing skills, requirement gaps, ATS flags → **Enter the hiring room**.
3. **Interview** → answer questions from the rotating panel (type or use the mic). STAR chips + “Better You” appear under each of your answers.
4. After ≥3 answers → **Deliberate**.
5. **Deliberation screen** → individual scores, key disagreement, consensus verdict, full debate transcript.

---

## Architecture (3 independent layers)

```
React + Vite  ──►  FastAPI  ──►  Layer 1: Resume Analysis (TF-IDF + skill vocab)
                           ──►  Layer 2: Interview Panel  (Gemini / fallback)
                           ──►  Layer 3: Visible Deliberation
                           ──►  SQLite (shared session memory)
```

Each layer can fail or be swapped without taking the others down — designed for reliable live demos.

### Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite |
| Backend | FastAPI (async) |
| AI | Gemini 2.0 / 2.5 Flash (optional) |
| Matching | Lightweight TF-IDF + curated skill vocabulary (no GPU needed) |
| DB | SQLite |
| Voice | Web Speech API |

---

## Project layout

```
hiring-room/
├── backend/
│   ├── main.py              # FastAPI routes
│   ├── ai_panel.py          # Personas, questions, STAR, rewriter, deliberation
│   ├── resume_analyzer.py   # PDF/DOCX extract + semantic match
│   ├── database.py          # SQLAlchemy models
│   ├── config.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/App.jsx          # Full UI (home → analysis → interview → deliberation)
│   ├── src/index.css
│   └── package.json
└── README.md
```

---

## Team (Girl Geeks 2026)

- **Divya Sharma**
- **Anagha Pai**
- **Harshitha N**

Convenor: Dr. R. China Appala Naidu (HOD, CSE)  
Faculty Coordinators: Dr. Parkavi A, Uzma Sulthana, Brunda G, Dr. Evangeline D  
Student Coordinator: Utkarsh Patel

---

## Why this stands out

Existing tools give **one score**.  
Real hiring is a **negotiation between perspectives**.  

The Hiring Room is the only coaching platform that shows the candidate the panel’s disagreement — the exact place where real decisions are made — and turns that into actionable feedback.

Built for first-generation job seekers, campus placement candidates, and professionals (especially women) returning to work.


## Platform upgrade (accounts + dashboard)

### Auth
- Register / Login with email + password (JWT, bcrypt)
- Per-user isolated sessions, scores, and history
- Profile + preferred language / target role

### App navigation (after login)
- **Dashboard** — scores, recommendations, recent activity
- **Resume** — upload + JD analysis (existing AI)
- **Interviews** — panel / behavioral / coding entry points
- **Performance** — score trends, strengths, gaps
- **History** — past sessions with detail view
- **Profile / Settings** — account + language

### Run
```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 → Sign up → Dashboard.

Demo mode and all existing AI panel features remain available inside **Resume** / **Interviews → workspace**.
