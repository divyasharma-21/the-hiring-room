"""
Lightweight JD–Resume semantic matcher.
Uses TF-IDF + keyword overlap so the demo works offline and without heavy models.
When Gemini is available it can enrich the narrative feedback.
"""

from __future__ import annotations

import re
import json
from collections import Counter
from typing import Any

# Common skill / tech vocabulary (expandable)
SKILL_VOCAB = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang", "rust",
    "react", "angular", "vue", "node", "nodejs", "express", "django", "flask", "fastapi",
    "spring", "springboot", "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "terraform", "ansible",
    "machine learning", "deep learning", "nlp", "computer vision", "tensorflow", "pytorch",
    "scikit-learn", "pandas", "numpy", "spark", "hadoop", "kafka", "airflow",
    "git", "ci/cd", "jenkins", "github actions", "linux", "rest", "graphql", "api",
    "agile", "scrum", "jira", "figma", "ui/ux", "html", "css", "tailwind", "bootstrap",
    "leadership", "communication", "teamwork", "problem solving", "ownership",
    "system design", "microservices", "distributed systems", "data structures", "algorithms",
    "unit testing", "integration testing", "tdd", "oop", "functional programming",
    "backend", "frontend", "full stack", "devops", "sre", "cloud", "security",
    "prompt engineering", "llm", "generative ai", "langchain", "vector database",
}


def extract_text_from_pdf(file_bytes: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(file_bytes))
    parts = []
    for page in reader.pages:
        t = page.extract_text() or ""
        parts.append(t)
    return "\n".join(parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    from io import BytesIO
    from docx import Document
    doc = Document(BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_resume_text(filename: str, file_bytes: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if name.endswith(".docx") or name.endswith(".doc"):
        return extract_text_from_docx(file_bytes)
    # plain text fallback
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def tokenize(text: str) -> list[str]:
    text = text.lower()
    # keep multi-word skills
    tokens = re.findall(r"[a-z+#.]{2,}", text)
    return tokens


STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "looking", "experience",
    "skills", "role", "team", "work", "working", "years", "year", "required",
    "preferred", "must", "have", "strong", "good", "excellent", "ability",
    "candidate", "position", "job", "description", "responsibilities",
}

def extract_skills(text: str) -> set[str]:
    text_l = text.lower()
    found = set()
    for skill in SKILL_VOCAB:
        # word-boundary-ish match for multi-word and single skills
        if re.search(rf"(?<![a-z]){re.escape(skill)}(?![a-z])", text_l):
            found.add(skill)
    # grab capitalized tech tokens that look like proper tech names
    for m in re.finditer(r"\b([A-Z][a-zA-Z+#.]{1,24})\b", text):
        w = m.group(1).lower()
        if len(w) > 2 and w not in STOPWORDS and w in SKILL_VOCAB:
            found.add(w)
    return found


def tfidf_vectors(docs: list[str]) -> tuple[list[Counter], Counter]:
    tokenized = [tokenize(d) for d in docs]
    df = Counter()
    for toks in tokenized:
        for t in set(toks):
            df[t] += 1
    n = len(docs)
    vectors = []
    for toks in tokenized:
        tf = Counter(toks)
        vec = Counter()
        for t, c in tf.items():
            idf = 1.0 + (n / (1 + df[t]))
            vec[t] = (c / max(len(toks), 1)) * idf
        vectors.append(vec)
    return vectors, df


def cosine(a: Counter, b: Counter) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return float(dot / (na * nb))



_MSG = {
    "en": {
        "ats_table": "Possible multi-column or table layout — ATS may scramble order.",
        "ats_ascii": "Non-ASCII characters detected; some ATS parsers struggle with special symbols.",
        "ats_email": "No email address detected — contact info may be missing or image-based.",
        "ats_short": "Resume text is very short — content may be locked in images or poorly extracted.",
        "ats_exp": "Limited 'Experience' section signals found.",
        "ats_ok": "No major ATS formatting risk flags detected.",
        "empty": "Resume or job description is empty.",
        "insufficient": "Insufficient text to analyze.",
        "area_missing": "Add evidence for missing skills: {skills}.",
        "area_weak": "{n} JD requirement(s) have weak or no supporting evidence on the resume.",
        "area_low": "Overall semantic alignment is low — tailor summary and bullets to the JD language.",
        "area_strong": "Strong alignment. Polish quantifiable impact statements for interviews.",
        "summary": "Semantic similarity {sim}%. {match} skills overlap with the JD; {missing} appear missing. Composite match score: {score}/100.",
    },
    "hi": {
        "ats_table": "संभव मल्टी-कॉलम या टेबल लेआउट — ATS क्रम बिगाड़ सकता है।",
        "ats_ascii": "गैर-ASCII अक्षर मिले; कुछ ATS विशेष चिह्नों से जूझते हैं।",
        "ats_email": "ईमेल पता नहीं मिला — संपर्क जानकारी छूट सकती है या छवि में हो।",
        "ats_short": "रिज्यूमे टेक्स्ट बहुत छोटा है — सामग्री छवियों में लॉक हो सकती है।",
        "ats_exp": "'Experience' सेक्शन के संकेत सीमित हैं।",
        "ats_ok": "कोई बड़ा ATS फ़ॉर्मेटिंग जोखिम नहीं मिला।",
        "empty": "रिज्यूमे या जॉब विवरण खाली है।",
        "insufficient": "विश्लेषण के लिए पर्याप्त टेक्स्ट नहीं।",
        "area_missing": "गायब स्किल्स के लिए प्रमाण जोड़ें: {skills}.",
        "area_weak": "{n} JD आवश्यकता(ओं) का रिज्यूमे पर कमजोर या कोई समर्थन नहीं।",
        "area_low": "समग्र अर्थ संरेखण कम है — सारांश और बुलेट्स को JD भाषा के अनुसार ढालें।",
        "area_strong": "मजबूत संरेखण। इंटरव्यू के लिए मापने योग्य प्रभाव वाक्य निखारें।",
        "summary": "अर्थ समानता {sim}%. JD से {match} स्किल्स मेल खाते हैं; {missing} गायब दिखते हैं। समग्र मैच स्कोर: {score}/100.",
    },
    "kn": {
        "ats_table": "ಬಹು-ಕಾಲಮ್ ಅಥವಾ ಟೇಬಲ್ ಲೇಔಟ್ ಇರಬಹುದು — ATS ಕ್ರಮ ತಪ್ಪಿಸಬಹುದು.",
        "ats_ascii": "Non-ASCII ಅಕ್ಷರಗಳು ಪತ್ತೆಯಾಗಿವೆ; ಕೆಲವು ATS ವಿಶೇಷ ಚಿಹ್ನೆಗಳೊಂದಿಗೆ ಹೋರಾಡುತ್ತವೆ.",
        "ats_email": "ಇಮೇಲ್ ವಿಳಾಸ ಕಂಡುಬಂದಿಲ್ಲ — ಸಂಪರ್ಕ ಮಾಹಿತಿ ಕಾಣೆಯಾಗಿರಬಹುದು.",
        "ats_short": "ರೆಸ್ಯೂಮ್ ಪಠ್ಯ ತುಂಬಾ ಚಿಕ್ಕದು — ವಿಷಯ ಚಿತ್ರಗಳಲ್ಲಿ ಲಾಕ್ ಆಗಿರಬಹುದು.",
        "ats_exp": "'Experience' ವಿಭಾಗ ಸಂಕೇತಗಳು ಸೀಮಿತ.",
        "ats_ok": "ದೊಡ್ಡ ATS ಫಾರ್ಮ್ಯಾಟಿಂಗ್ ಅಪಾಯಗಳು ಕಂಡುಬಂದಿಲ್ಲ.",
        "empty": "ರೆಸ್ಯೂಮ್ ಅಥವಾ ಉದ್ಯೋಗ ವಿವರ ಖಾಲಿ.",
        "insufficient": "ವಿಶ್ಲೇಷಣೆಗೆ ಸಾಕಷ್ಟು ಪಠ್ಯವಿಲ್ಲ.",
        "area_missing": "ಕಾಣೆಯಾದ ಕೌಶಲ್ಯಗಳಿಗೆ ಸಾಕ್ಷ್ಯ ಸೇರಿಸಿ: {skills}.",
        "area_weak": "{n} JD ಅಗತ್ಯ(ಗಳು) ರೆಸ್ಯೂಮ್‌ನಲ್ಲಿ ದುರ್ಬಲ ಅಥವಾ ಇಲ್ಲ.",
        "area_low": "ಒಟ್ಟು ಅರ್ಥ ಹೊಂದಾಣಿಕೆ ಕಡಿಮೆ — ಸಾರಾಂಶ ಮತ್ತು ಬುಲೆಟ್‌ಗಳನ್ನು JD ಭಾಷೆಗೆ ಹೊಂದಿಸಿ.",
        "area_strong": "ಬಲವಾದ ಹೊಂದಾಣಿಕೆ. ಸಂದರ್ಶನಕ್ಕಾಗಿ ಅಳೆಯಬಹುದಾದ ಪ್ರಭಾವ ವಾಕ್ಯಗಳನ್ನು ಪಾಲಿಷ್ ಮಾಡಿ.",
        "summary": "ಅರ್ಥ ಸಾಮ್ಯತೆ {sim}%. JD ಜೊತೆ {match} ಕೌಶಲ್ಯ ಹೊಂದಿಕೆ; {missing} ಕಾಣೆಯಾಗಿವೆ. ಒಟ್ಟು ಸ್ಕೋರ್: {score}/100.",
    },
}

def _m(lang: str, key: str, **kw) -> str:
    lang = (lang or "en").lower()
    if lang not in _MSG:
        lang = "en"
    s = _MSG[lang].get(key) or _MSG["en"].get(key, key)
    try:
        return s.format(**kw)
    except Exception:
        return s


def ats_flags(text: str, language: str = "en") -> list[dict[str, str]]:
    flags = []
    if text.count("\t") > 10 or len(re.findall(r"\|.*\|.*\|", text)) > 3:
        flags.append({"level": "warning", "message": _m(language, "ats_table")})
    if len(re.findall(r"[^\x00-\x7F]", text)) > 20:
        flags.append({"level": "info", "message": _m(language, "ats_ascii")})
    if not re.search(r"@\w+\.\w+", text):
        flags.append({"level": "warning", "message": _m(language, "ats_email")})
    if len(text.split()) < 80:
        flags.append({"level": "warning", "message": _m(language, "ats_short")})
    if re.search(r"curriculum vitae|resume\s+of", text, re.I) and text.lower().count("experience") < 1:
        flags.append({"level": "info", "message": _m(language, "ats_exp")})
    if not flags:
        flags.append({"level": "success", "message": _m(language, "ats_ok")})
    return flags


def analyze_resume(resume_text: str, jd_text: str, language: str = "en") -> dict[str, Any]:
    resume_text = (resume_text or "").strip()
    jd_text = (jd_text or "").strip()
    language = (language or "en").lower()

    if not resume_text or not jd_text:
        return {
            "overall_score": 0,
            "semantic_similarity": 0,
            "matching_skills": [],
            "missing_skills": [],
            "extra_skills": [],
            "gaps": [],
            "ats_flags": [{"level": "error", "message": _m(language, "empty")}],
            "summary": _m(language, "insufficient"),
            "areas_to_improve": [],
        }

    vectors, _ = tfidf_vectors([resume_text, jd_text])
    sim = cosine(vectors[0], vectors[1])

    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    matching = sorted(resume_skills & jd_skills)
    missing = sorted(jd_skills - resume_skills)
    extra = sorted(resume_skills - jd_skills)

    jd_lines = [l.strip(" -•*\t") for l in jd_text.splitlines() if len(l.strip()) > 25]
    gaps = []
    for line in jd_lines[:12]:
        line_skills = extract_skills(line)
        covered = line_skills & resume_skills
        coverage = len(covered) / max(len(line_skills), 1) if line_skills else 0.5
        line_toks = set(tokenize(line))
        res_toks = set(tokenize(resume_text))
        lex = len(line_toks & res_toks) / max(len(line_toks), 1)
        score = 0.6 * coverage + 0.4 * lex
        status = "met" if score >= 0.45 else "partial" if score >= 0.2 else "missing"
        gaps.append({
            "requirement": line[:180],
            "status": status,
            "coverage_score": round(score, 2),
            "matched_signals": sorted(covered)[:6],
        })

    skill_ratio = len(matching) / max(len(jd_skills), 1)
    overall = round(100 * (0.55 * sim + 0.45 * skill_ratio), 1)
    overall = max(0, min(100, overall))

    areas = []
    if missing:
        areas.append(_m(language, "area_missing", skills=", ".join(missing[:8])))
    weak_gaps = [g for g in gaps if g["status"] != "met"]
    if weak_gaps:
        areas.append(_m(language, "area_weak", n=len(weak_gaps)))
    if overall < 55:
        areas.append(_m(language, "area_low"))
    if not areas:
        areas.append(_m(language, "area_strong"))

    summary = _m(
        language, "summary",
        sim=f"{sim*100:.0f}",
        match=len(matching),
        missing=len(missing),
        score=overall,
    )

    return {
        "overall_score": overall,
        "semantic_similarity": round(sim, 3),
        "matching_skills": matching[:25],
        "missing_skills": missing[:20],
        "extra_skills": extra[:15],
        "gaps": gaps,
        "ats_flags": ats_flags(resume_text, language=language),
        "summary": summary,
        "areas_to_improve": areas,
    }

