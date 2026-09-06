"""
Tech coding micro-round for The Hiring Room.
1) Debug-the-snippet (5 levels)
2) Mini coding (5 levels)
Static Tech Lead review — no code execution.
Correct solutions score high; better_code only shown when improvement is needed.
"""

from __future__ import annotations

import random
import re
from typing import Any

from ai_panel import _call_gemini, _gemini_available, _parse_json_loose, _L

# ---------- Debug bank (5 difficulties) ----------

DEBUG_PROBLEMS = [
    {
        "id": "dbg_sum_even",
        "title": "Sum of even numbers",
        "difficulty": "easy",
        "language": "python",
        "prompt": (
            "Production helper used in a billing batch job. "
            "It should return the sum of all even numbers in a list. Find and fix the bug."
        ),
        "buggy_code": """def sum_even(nums):
    total = 0
    for n in nums:
        if n % 2 == 1:  # bug: selects odds
            total += n
    return total
""",
        "reference_fix": """def sum_even(nums):
    total = 0
    for n in nums:
        if n % 2 == 0:
            total += n
    return total
""",
        "hint": "Check which numbers are being selected by the condition.",
        "topics": ["loops", "conditionals"],
        "accept_patterns": [r"%\s*2\s*==\s*0", r"not\s*\(\s*n\s*%\s*2\s*\)", r"n\s*%\s*2\s*==\s*0"],
        "reject_if": [r"%\s*2\s*==\s*1"],
    },
    {
        "id": "dbg_off_by_one",
        "title": "First n squares",
        "difficulty": "easy",
        "language": "python",
        "prompt": (
            "Internal analytics helper should return squares of 1..n inclusive. "
            "QA reported missing the last value."
        ),
        "buggy_code": """def squares(n):
    out = []
    for i in range(n):  # bug: 0..n-1
        out.append(i * i)
    return out
""",
        "reference_fix": """def squares(n):
    out = []
    for i in range(1, n + 1):
        out.append(i * i)
    return out
""",
        "hint": "Does range include n? Should squares start at 1 or 0?",
        "topics": ["off-by-one", "range"],
        "accept_patterns": [r"range\s*\(\s*1\s*,\s*n\s*\+\s*1\s*\)", r"range\s*\(\s*1\s*,\s*n\s*\+\s*1"],
        "reject_if": [],
    },
    {
        "id": "dbg_null",
        "title": "Username length",
        "difficulty": "easy",
        "language": "python",
        "prompt": (
            "API middleware calls this to log username length. "
            "It should return 0 if user is missing or name is absent — currently crashes."
        ),
        "buggy_code": """def username_len(user):
    return len(user["name"])
""",
        "reference_fix": """def username_len(user):
    if not user:
        return 0
    name = user.get("name") or ""
    return len(name)
""",
        "hint": "Guard against None and missing keys.",
        "topics": ["null-safety", "dicts"],
        "accept_patterns": [r"\.get\s*\(", r"if\s+not\s+user", r"is\s+None"],
        "reject_if": [],
    },
    {
        "id": "dbg_mutate",
        "title": "Safe default list",
        "difficulty": "medium",
        "language": "python",
        "prompt": (
            "Shared utility appends tags to a bucket. "
            "Callers report tags leaking across requests — classic Python pitfall."
        ),
        "buggy_code": """def append_item(x, bucket=[]):
    bucket.append(x)
    return bucket
""",
        "reference_fix": """def append_item(x, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(x)
    return bucket
""",
        "hint": "Mutable default arguments are created once and shared.",
        "topics": ["defaults", "mutability"],
        "accept_patterns": [r"bucket\s*=\s*None", r"if\s+bucket\s+is\s+None"],
        "reject_if": [r"bucket\s*=\s*\[\s*\]"],
    },
    {
        "id": "dbg_race_flag",
        "title": "Idempotent mark-processed",
        "difficulty": "hard",
        "language": "python",
        "prompt": (
            "Worker marks job IDs as processed. "
            "Should return True only the first time an id is seen; False if already processed. "
            "Current version always returns True."
        ),
        "buggy_code": """_seen = set()

def mark_processed(job_id):
    _seen.add(job_id)
    return True  # bug: ignores prior membership
""",
        "reference_fix": """_seen = set()

def mark_processed(job_id):
    if job_id in _seen:
        return False
    _seen.add(job_id)
    return True
""",
        "hint": "Check membership before adding.",
        "topics": ["sets", "idempotency"],
        "accept_patterns": [r"if\s+job_id\s+in\s+_seen", r"if\s+.*in\s+_seen"],
        "reject_if": [],
    },
]

# ---------- Coding bank (5 difficulties) ----------

CODING_PROBLEMS = [
    {
        "id": "cod_dedupe",
        "title": "Stable dedupe",
        "difficulty": "easy",
        "language": "python",
        "prompt": (
            "Ingestion pipeline receives duplicate event ids. "
            "Implement dedupe(items) → new list with duplicates removed, preserving first-seen order."
        ),
        "starter": """def dedupe(items):
    # preserve order, drop later duplicates
    pass
""",
        "reference": """def dedupe(items):
    seen = set()
    out = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out
""",
        "topics": ["arrays", "sets"],
        "skills": ["python"],
        "must_have": [r"def\s+dedupe", r"return"],
        "good_patterns": [r"seen", r"set\s*\(", r"if\s+.+\s+in\s+"],
    },
    {
        "id": "cod_freq",
        "title": "Top character frequency",
        "difficulty": "easy",
        "language": "python",
        "prompt": (
            "Log-analysis helper: return the most frequent non-space character in string s. "
            "If tied, any of the top characters is fine."
        ),
        "starter": """def top_char(s):
    # ignore spaces; return one character
    pass
""",
        "reference": """def top_char(s):
    counts = {}
    for ch in s:
        if ch == " ":
            continue
        counts[ch] = counts.get(ch, 0) + 1
    if not counts:
        return ""
    return max(counts, key=counts.get)
""",
        "topics": ["strings", "counting"],
        "skills": ["python"],
        "must_have": [r"def\s+top_char", r"return"],
        "good_patterns": [r"for\s+", r"dict|Counter|\{", r"max\s*\("],
    },
    {
        "id": "cod_two_sum",
        "title": "Two sum indices",
        "difficulty": "medium",
        "language": "python",
        "prompt": (
            "Payment matching: given nums and target, return indices of two numbers that add to target. "
            "Exactly one solution exists. Prefer O(n) time."
        ),
        "starter": """def two_sum(nums, target):
    # return [i, j]
    pass
""",
        "reference": """def two_sum(nums, target):
    need = {}
    for i, n in enumerate(nums):
        if n in need:
            return [need[n], i]
        need[target - n] = i
    return []
""",
        "topics": ["hash map", "arrays"],
        "skills": ["python", "algorithms"],
        "must_have": [r"def\s+two_sum", r"return"],
        "good_patterns": [r"enumerate|for\s+", r"dict|\{", r"target"],
    },
    {
        "id": "cod_api_validate",
        "title": "Validate API payload",
        "difficulty": "medium",
        "language": "python",
        "prompt": (
            "FastAPI dependency style: implement validate_user(payload: dict) -> tuple[bool, str]. "
            "Require name (non-empty str) and age (int 18..120). "
            "Return (True, 'ok') or (False, reason)."
        ),
        "starter": """def validate_user(payload):
    # return (True, "ok") or (False, "reason")
    pass
""",
        "reference": """def validate_user(payload):
    if not isinstance(payload, dict):
        return (False, "payload must be a dict")
    name = payload.get("name")
    age = payload.get("age")
    if not isinstance(name, str) or not name.strip():
        return (False, "name must be a non-empty string")
    if not isinstance(age, int) or age < 18 or age > 120:
        return (False, "age must be an int between 18 and 120")
    return (True, "ok")
""",
        "topics": ["validation", "apis"],
        "skills": ["python", "api", "fastapi"],
        "must_have": [r"def\s+validate_user", r"return"],
        "good_patterns": [r"name", r"age", r"False|True"],
    },
    {
        "id": "cod_merge_intervals",
        "title": "Merge overlapping intervals",
        "difficulty": "hard",
        "language": "python",
        "prompt": (
            "Calendar service: merge overlapping [start, end] intervals. "
            "Input is a list of pairs; return merged sorted intervals."
        ),
        "starter": """def merge_intervals(intervals):
    # intervals: List[List[int]] e.g. [[1,3],[2,6],[8,10]]
    pass
""",
        "reference": """def merge_intervals(intervals):
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
""",
        "topics": ["sorting", "intervals"],
        "skills": ["python", "algorithms"],
        "must_have": [r"def\s+merge_intervals", r"return"],
        "good_patterns": [r"sort", r"for\s+", r"max\s*\("],
    },
]



SUPPORTED_LANGUAGES = ["python", "javascript", "java", "cpp"]

# Minimal multi-language templates for coding starters / debug samples
LANGUAGE_TEMPLATES = {
    "python": {
        "comment": "#",
        "sum_even_bug": """def sum_even(nums):
    total = 0
    for n in nums:
        if n % 2 == 1:
            total += n
    return total
""",
        "sum_even_fix": """def sum_even(nums):
    total = 0
    for n in nums:
        if n % 2 == 0:
            total += n
    return total
""",
        "two_sum_starter": """def two_sum(nums, target):
    # return [i, j]
    pass
""",
        "two_sum_ref": """def two_sum(nums, target):
    need = {}
    for i, n in enumerate(nums):
        if n in need:
            return [need[n], i]
        need[target - n] = i
    return []
""",
    },
    "javascript": {
        "comment": "//",
        "sum_even_bug": """function sumEven(nums) {
  let total = 0;
  for (const n of nums) {
    if (n % 2 === 1) {
      total += n;
    }
  }
  return total;
}
""",
        "sum_even_fix": """function sumEven(nums) {
  let total = 0;
  for (const n of nums) {
    if (n % 2 === 0) {
      total += n;
    }
  }
  return total;
}
""",
        "two_sum_starter": """function twoSum(nums, target) {
  // return [i, j]
}
""",
        "two_sum_ref": """function twoSum(nums, target) {
  const need = new Map();
  for (let i = 0; i < nums.length; i++) {
    const n = nums[i];
    if (need.has(n)) return [need.get(n), i];
    need.set(target - n, i);
  }
  return [];
}
""",
    },
    "java": {
        "comment": "//",
        "sum_even_bug": """public class Solution {
  public int sumEven(int[] nums) {
    int total = 0;
    for (int n : nums) {
      if (n % 2 == 1) {
        total += n;
      }
    }
    return total;
  }
}
""",
        "sum_even_fix": """public class Solution {
  public int sumEven(int[] nums) {
    int total = 0;
    for (int n : nums) {
      if (n % 2 == 0) {
        total += n;
      }
    }
    return total;
  }
}
""",
        "two_sum_starter": """public class Solution {
  public int[] twoSum(int[] nums, int target) {
    // return {i, j}
    return new int[]{-1, -1};
  }
}
""",
        "two_sum_ref": """public class Solution {
  public int[] twoSum(int[] nums, int target) {
    java.util.Map<Integer, Integer> need = new java.util.HashMap<>();
    for (int i = 0; i < nums.length; i++) {
      if (need.containsKey(nums[i])) {
        return new int[]{need.get(nums[i]), i};
      }
      need.put(target - nums[i], i);
    }
    return new int[]{};
  }
}
""",
    },
    "cpp": {
        "comment": "//",
        "sum_even_bug": """#include <vector>
using namespace std;

int sumEven(vector<int>& nums) {
    int total = 0;
    for (int n : nums) {
        if (n % 2 == 1) {
            total += n;
        }
    }
    return total;
}
""",
        "sum_even_fix": """#include <vector>
using namespace std;

int sumEven(vector<int>& nums) {
    int total = 0;
    for (int n : nums) {
        if (n % 2 == 0) {
            total += n;
        }
    }
    return total;
}
""",
        "two_sum_starter": """#include <vector>
#include <unordered_map>
using namespace std;

vector<int> twoSum(vector<int>& nums, int target) {
    // return {i, j}
    return {};
}
""",
        "two_sum_ref": """#include <vector>
#include <unordered_map>
using namespace std;

vector<int> twoSum(vector<int>& nums, int target) {
    unordered_map<int, int> need;
    for (int i = 0; i < (int)nums.size(); i++) {
        if (need.count(nums[i])) return {need[nums[i]], i};
        need[target - nums[i]] = i;
    }
    return {};
}
""",
    },
}


def apply_language(problem: dict, language: str) -> dict:
    """Return a copy of problem with language-specific code when available."""
    lang = (language or "python").lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = "python"
    p = dict(problem)
    p["language"] = lang
    templates = LANGUAGE_TEMPLATES.get(lang) or LANGUAGE_TEMPLATES["python"]
    pid = p.get("id", "")

    # Map a few problems to multi-lang templates; others stay Python with note
    if pid == "dbg_sum_even":
        p["buggy_code"] = templates["sum_even_bug"]
        p["reference_fix"] = templates["sum_even_fix"]
    elif pid == "cod_two_sum":
        p["starter"] = templates["two_sum_starter"]
        p["reference"] = templates["two_sum_ref"]
    elif lang != "python":
        # For problems without full ports, keep logic in Python but label language choice
        # and prefix a note in prompt so candidate can solve in chosen language
        note = f" Implement your solution in {lang}. Indentation and style should match {lang} conventions."
        p["prompt"] = (p.get("prompt") or "") + note
        if p.get("starter"):
            p["starter"] = f"{templates['comment']} Write your {lang} solution below\n" + (p.get("starter") or "")
        if p.get("buggy_code"):
            p["buggy_code"] = f"{templates['comment']} Port/fix this logic in {lang}\n" + (p.get("buggy_code") or "")
    return p


def _filter_bank(bank: list, difficulty: str | None = None, exclude_ids: list | None = None) -> list:
    exclude = set(exclude_ids or [])
    out = [p for p in bank if p.get("id") not in exclude]
    if difficulty:
        d = difficulty.lower().strip()
        # Strict: only this difficulty; no silent fallback (user chose per question)
        return [p for p in out if (p.get("difficulty") or "").lower() == d]
    return out


def pick_debug_problem(
    analysis: dict | None = None,
    difficulty: str | None = None,
    exclude_ids: list | None = None,
    language: str = "python",
) -> dict | None:
    pool = _filter_bank(DEBUG_PROBLEMS, difficulty=difficulty, exclude_ids=exclude_ids)
    if not pool:
        return None
    return apply_language(dict(random.choice(pool)), language)


def pick_coding_problem(
    analysis: dict | None = None,
    difficulty: str | None = None,
    exclude_ids: list | None = None,
    language: str = "python",
) -> dict | None:
    analysis = analysis or {}
    pool = _filter_bank(CODING_PROBLEMS, difficulty=difficulty, exclude_ids=exclude_ids)
    if not pool:
        return None

    missing = {s.lower() for s in (analysis.get("missing_skills") or [])}
    matching = {s.lower() for s in (analysis.get("matching_skills") or [])}
    skills = missing | matching

    # Prefer JD-aligned problem if still available in pool
    preferred_ids = []
    if skills & {"api", "fastapi", "django", "flask", "backend"}:
        preferred_ids.append("cod_api_validate")
    if skills & {"algorithms", "data structures"}:
        preferred_ids.extend(["cod_two_sum", "cod_merge_intervals"])
    preferred = [p for p in pool if p.get("id") in preferred_ids]
    if preferred and not difficulty:
        return apply_language(dict(random.choice(preferred)), language)
    return apply_language(dict(random.choice(pool)), language)




def generate_ai_problem(
    mode: str = "debug",
    difficulty: str | None = "easy",
    language: str = "python",
    ui_language: str = "en",
    analysis: dict | None = None,
    exclude_ids: list | None = None,
) -> dict | None:
    """Generate a fresh debug/coding problem via Gemini in the UI language.
    Falls back to the fixed bank if Gemini is unavailable.
    """
    mode = (mode or "debug").lower()
    difficulty = (difficulty or "easy").lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "easy"
    language = (language or "python").lower()
    if language not in ("python", "javascript", "java", "cpp"):
        language = "python"
    ui = (ui_language or "en").lower()
    if ui not in ("en", "hi", "kn"):
        ui = "en"

    lang_name = {"en": "English", "hi": "Hindi", "kn": "Kannada"}.get(ui, "English")
    analysis = analysis or {}
    skills = (analysis.get("missing_skills") or [])[:6] + (analysis.get("matching_skills") or [])[:4]
    skill_hint = ", ".join(skills) if skills else "general programming, APIs, data structures"

    if _gemini_available():
        if mode == "debug":
            system = (
                f"You are a senior Tech Lead writing a SHORT debugging interview exercise. "
                f"Respond in {lang_name} for title, prompt, and hint. "
                f"Code (buggy_code and reference) must stay in {language}. "
                "Return STRICT JSON only with keys: "
                "id, title, difficulty, language, prompt, buggy_code, reference, hint, topics. "
                "id must be a short unique slug like dbg_ai_<random>. "
                "difficulty must match the requested level. "
                "buggy_code: a short realistic buggy function (10-25 lines). "
                "reference: corrected version. "
                "prompt: what the function should do and what is wrong (2-4 sentences). "
                "hint: one short coaching hint. "
                "topics: array of 1-3 topic tags in English."
            )
            prompt = (
                f"Create one {difficulty} debug problem in {language}. "
                f"Relevant skills: {skill_hint}. "
                f"Make it realistic for a production interview, not a toy puzzle. Invent a FRESH problem every time — never recycle the same toy example. Vary topics (strings, arrays, APIs, parsing, hashing, edge cases)."
            )
        else:
            system = (
                f"You are a senior Tech Lead writing a SHORT coding interview exercise. "
                f"Respond in {lang_name} for title, prompt, and hint. "
                f"Code (starter and reference) must stay in {language}. "
                "Return STRICT JSON only with keys: "
                "id, title, difficulty, language, prompt, starter, reference, hint, topics. "
                "id must be a short unique slug like cod_ai_<random>. "
                "starter: function signature with pass/TODO. "
                "reference: complete correct solution. "
                "prompt: clear requirements (2-4 sentences). "
                "hint: one short coaching hint. "
                "topics: array of 1-3 topic tags in English."
            )
            prompt = (
                f"Create one {difficulty} coding problem in {language}. "
                f"Relevant skills: {skill_hint}. "
                f"Keep the scope small enough for a 10-15 minute exercise. Invent a FRESH problem every time with a unique title — do not reuse classic leetcode clones verbatim."
            )
        raw = _call_gemini(prompt, system=system, temperature=0.7, language=ui)
        data = _parse_json_loose(raw)
        if isinstance(data, dict) and data.get("title") and (data.get("prompt") or data.get("buggy_code") or data.get("starter")):
            data["difficulty"] = difficulty
            data["language"] = language
            data["id"] = data.get("id") or f"{'dbg' if mode == 'debug' else 'cod'}_ai_{random.randint(1000,9999)}"
            data["ai_generated"] = True
            if mode == "debug":
                data.setdefault("buggy_code", data.get("starter") or "")
                data.setdefault("reference", data.get("reference") or "")
            else:
                data.setdefault("starter", data.get("starter") or data.get("buggy_code") or "")
                data.setdefault("reference", data.get("reference") or "")
            data.setdefault("topics", [])
            data.setdefault("hint", "")
            return data

    # Fallback to fixed bank
    if mode == "debug":
        return pick_debug_problem(analysis, difficulty=difficulty, exclude_ids=exclude_ids, language=language)
    return pick_coding_problem(analysis, difficulty=difficulty, exclude_ids=exclude_ids, language=language)


def _norm_code(s: str) -> str:
    s = s or ""
    s = re.sub(r"#.*", "", s)
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    s = re.sub(r"'''[\s\S]*?'''", "", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _looks_like_pass_only(code: str) -> bool:
    body = re.sub(r"#.*", "", code or "")
    body = re.sub(r'"""[\s\S]*?"""', "", body)
    body = re.sub(r"'''[\s\S]*?'''", "", body)
    # strip def line
    body = re.sub(r"def\s+\w+\s*\([^)]*\)\s*:", "", body)
    body = body.strip().lower()
    return body in ("pass", "", "pass\n") or body.replace(" ", "") in ("pass",)


def _patterns_hit(code: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if p and re.search(p, code, re.I | re.M))


def review_debug(problem: dict, submission: str, language: str = "en") -> dict[str, Any]:
    submission = (submission or "").strip()
    if not submission:
        return _empty_debug(problem)

    # Gemini path with strict instructions
    if _gemini_available():
        data = _gemini_debug_review(problem, submission, language=language)
        if data:
            return data

    return _heuristic_debug_review(problem, submission, language=language)


def review_coding(problem: dict, submission: str, language: str = "en") -> dict[str, Any]:
    submission = (submission or "").strip()
    if not submission:
        return _empty_coding(problem)

    if _gemini_available():
        data = _gemini_coding_review(problem, submission, language=language)
        if data:
            return data

    return _heuristic_coding_review(problem, submission, language=language)


def _gemini_debug_review(problem: dict, submission: str, language: str = "en") -> dict | None:
    system = (
        "You are a Technical Lead reviewing a bug-fix submission for a hiring coach product. "
        "Compare the candidate code to the intended fix. "
        "If the candidate correctly fixed the bug, score 88-100, set bug_identified=true, "
        "and set better_code to null or omit it (do NOT paste their code back as 'better'). "
        "Only provide better_code when the fix is wrong or incomplete — then show a clean correct version. "
        "Feedback must reference what THEY wrote. "
        "Return strict JSON: "
        '{"score":0-100,"verdict":"strong|ok|weak","bug_identified":true/false,'
        '"fix_quality":"clear|partial|unclear","feedback":"2-4 sentences about their code",'
        '"strengths":["..."],"concerns":["..."],"better_code":null or "code"}'
    )
    prompt = (
        f"Title: {problem.get('title')}\nPrompt: {problem.get('prompt')}\n\n"
        f"Buggy original:\n{problem.get('buggy_code')}\n\n"
        f"Reference correct fix:\n{problem.get('reference_fix')}\n\n"
        f"Candidate submission:\n{submission}\n"
    )
    raw = _call_gemini(prompt, system=system, temperature=0.2, language=language)
    data = _parse_json_loose(raw)
    if not isinstance(data, dict) or "score" not in data:
        return None
    return _finalize_debug(problem, submission, data)


def _gemini_coding_review(problem: dict, submission: str, language: str = "en") -> dict | None:
    system = (
        "You are a Technical Lead reviewing a short coding solution (static review, no execution). "
        "If the solution is substantially correct and complete, score 85-100 and set better_code to null. "
        "Do NOT return the candidate's same code as better_code. "
        "Only include better_code when there is a real improvement to show. "
        "Feedback must be specific to their implementation choices. "
        "Return strict JSON: "
        '{"score":0-100,"verdict":"strong|ok|weak","correctness":"likely|partial|unlikely",'
        '"edge_cases":"good|partial|poor","clarity":"clear|messy",'
        '"complexity_notes":"one line","feedback":"3-5 sentences",'
        '"strengths":["..."],"concerns":["..."],"better_code":null or "code"}'
    )
    prompt = (
        f"Title: {problem.get('title')}\nPrompt: {problem.get('prompt')}\n\n"
        f"Reference solution:\n{problem.get('reference')}\n\n"
        f"Candidate code:\n{submission}\n"
    )
    raw = _call_gemini(prompt, system=system, temperature=0.25, language=language)
    data = _parse_json_loose(raw)
    if not isinstance(data, dict) or "score" not in data:
        return None
    return _finalize_coding(problem, submission, data)


def _finalize_debug(problem: dict, submission: str, data: dict) -> dict:
    score = int(data.get("score") or 0)
    bug_ok = bool(data.get("bug_identified"))
    better = data.get("better_code")
    # If high score / bug fixed, never echo same code as better
    if score >= 85 or bug_ok:
        if better and _norm_code(better) == _norm_code(submission):
            better = None
        if score >= 90:
            better = None
    else:
        if not better or _norm_code(str(better)) == _norm_code(submission):
            better = problem.get("reference_fix")
    data["score"] = max(0, min(100, score))
    data["better_code"] = better
    data.setdefault("strengths", [])
    data.setdefault("concerns", [])
    data.setdefault("feedback", "")
    data.setdefault("verdict", "strong" if score >= 80 else "ok" if score >= 55 else "weak")
    data.setdefault("fix_quality", "clear" if bug_ok else "partial")
    data["bug_identified"] = bug_ok
    return data


def _finalize_coding(problem: dict, submission: str, data: dict) -> dict:
    score = int(data.get("score") or 0)
    better = data.get("better_code")
    if score >= 85:
        if better and _norm_code(str(better)) == _norm_code(submission):
            better = None
        if score >= 90:
            better = None
    else:
        if not better or _norm_code(str(better)) == _norm_code(submission):
            better = problem.get("reference")
    data["score"] = max(0, min(100, score))
    data["better_code"] = better
    data.setdefault("strengths", [])
    data.setdefault("concerns", [])
    data.setdefault("feedback", "")
    data.setdefault("verdict", "strong" if score >= 80 else "ok" if score >= 55 else "weak")
    return data


def _heuristic_debug_review(problem: dict, submission: str, language: str = "en") -> dict[str, Any]:
    if _looks_like_pass_only(submission) and "def " not in submission:
        return _empty_debug(problem)

    accept = problem.get("accept_patterns") or []
    reject = problem.get("reject_if") or []
    hits = _patterns_hit(submission, accept)
    rejects = _patterns_hit(submission, reject)

    # Still identical to buggy?
    same_as_bug = _norm_code(submission) == _norm_code(problem.get("buggy_code") or "")
    ref = problem.get("reference_fix") or ""
    close_to_ref = _norm_code(submission) == _norm_code(ref)

    bug_identified = False
    score = 25
    strengths = []
    concerns = []

    if same_as_bug:
        concerns.append(_L(language, "coding_same_bug"))
        score = 20
    elif close_to_ref or (hits >= max(1, len(accept)) and rejects == 0):
        bug_identified = True
        score = 100
        strengths.append(_L(language, "coding_fixed"))
        strengths.append(_L(language, "coding_matches"))
    elif hits > 0 and rejects == 0:
        bug_identified = True
        score = 78
        strengths.append(_L(language, "coding_key_fix"))
        concerns.append(_L(language, "coding_minor"))
    elif hits > 0 and rejects > 0:
        score = 55
        concerns.append(_L(language, "coding_partial"))
        strengths.append(_L(language, "coding_direction"))
    else:
        score = 40
        concerns.append(_L(language, "coding_unconfirmed"))

    if "def " in submission:
        strengths.append(_L(language, "coding_structure"))
    if len(submission) > 20 and not same_as_bug:
        score = min(100, score + 3)

    verdict = "strong" if score >= 80 else "ok" if score >= 55 else "weak"
    title = problem.get("title") or ""
    if bug_identified and score >= 85:
        feedback = _L(language, "coding_fb_good", title=title)
        better = None
    elif bug_identified:
        feedback = _L(language, "coding_fb_partial", title=title)
        better = ref if score < 85 else None
    else:
        feedback = _L(language, "coding_fb_bad", title=title)
        better = ref

    return {
        "score": min(100, score),
        "verdict": verdict,
        "bug_identified": bug_identified,
        "fix_quality": "clear" if bug_identified and score >= 85 else "partial" if bug_identified else "unclear",
        "feedback": feedback,
        "strengths": strengths[:4],
        "concerns": concerns[:4],
        "better_code": better,
    }


def _heuristic_coding_review(problem: dict, submission: str, language: str = "en") -> dict[str, Any]:
    if _looks_like_pass_only(submission):
        return {
            "score": 15,
            "verdict": "weak",
            "correctness": "unlikely",
            "edge_cases": "poor",
            "clarity": "n/a",
            "complexity_notes": "Implement the body before discussing complexity.",
            "feedback": "Tech Lead: This is still the starter stub. Implement the function body and resubmit.",
            "strengths": [],
            "concerns": ["Unimplemented solution (pass/stub)"],
            "better_code": problem.get("reference"),
        }

    must = problem.get("must_have") or []
    good = problem.get("good_patterns") or []
    must_hits = _patterns_hit(submission, must)
    good_hits = _patterns_hit(submission, good)
    ref = problem.get("reference") or ""
    close_to_ref = _norm_code(submission) == _norm_code(ref)

    score = 30
    strengths = []
    concerns = []

    if must_hits >= len(must) and must:
        score += 25
        strengths.append("Required function shape and return are present")
    else:
        concerns.append("Missing expected function structure or return")

    score += min(30, good_hits * 12)
    if good_hits:
        strengths.append("Uses patterns appropriate for this problem")

    if close_to_ref:
        score = 100
        strengths.append("Approach aligns with a solid reference solution")
    elif must and must_hits >= len(must) and good and good_hits >= len(good):
        score = 100
        strengths.append("All required patterns and best-practice signals present")
    elif good_hits >= max(2, len(good) - 1) and must_hits >= len(must):
        score = max(score, 86)
        strengths.append("Likely correct core logic from static review")

    # Edge awareness
    edge = "poor"
    if re.search(r"empty|none|not\s+\w+|len\s*\(|if\s+not\s+", submission, re.I):
        edge = "partial"
        score += 5
        strengths.append("Some edge-case awareness")
    if re.search(r"isinstance|raise\s+|valueerror", submission, re.I):
        edge = "good"
        score += 5

    clarity = "clear" if len(submission) < 900 and "def " in submission else "messy"
    if clarity == "clear":
        score += 4

    score = max(0, min(100, score))
    correctness = "likely" if score >= 80 else "partial" if score >= 55 else "unlikely"
    verdict = "strong" if score >= 80 else "ok" if score >= 55 else "weak"

    if score >= 88:
        feedback = (
            f"Tech Lead: For “{problem.get('title')}”, your implementation looks solid on static review — "
            f"structure is clear and the approach matches the problem constraints. "
            f"I’d ask you to talk through one edge case in the panel, but the code itself is in good shape."
        )
        better = None
    elif score >= 70:
        feedback = (
            f"Tech Lead: Reasonable attempt on “{problem.get('title')}”. "
            f"Core idea is visible; harden edge cases and naming before production."
        )
        better = ref
    else:
        feedback = (
            f"Tech Lead: “{problem.get('title')}” needs more complete logic. "
            f"Focus on the main path first, then empty inputs and complexity."
        )
        better = ref

    # Never echo identical code as better
    if better and _norm_code(str(better)) == _norm_code(submission):
        better = None

    return {
        "score": score,
        "verdict": verdict,
        "correctness": correctness,
        "edge_cases": edge,
        "clarity": clarity,
        "complexity_notes": (
            "Be ready to state time/space complexity in one sentence during the panel."
        ),
        "feedback": feedback,
        "strengths": strengths[:4],
        "concerns": concerns[:4],
        "better_code": better,
    }


def _empty_debug(problem: dict) -> dict[str, Any]:
    return {
        "score": 0,
        "verdict": "incomplete",
        "bug_identified": False,
        "fix_quality": "n/a",
        "feedback": "No solution submitted.",
        "strengths": [],
        "concerns": ["Empty submission"],
        "better_code": problem.get("reference_fix"),
    }


def _empty_coding(problem: dict) -> dict[str, Any]:
    return {
        "score": 0,
        "verdict": "incomplete",
        "correctness": "unknown",
        "edge_cases": "not addressed",
        "clarity": "n/a",
        "complexity_notes": "",
        "feedback": "No code submitted.",
        "strengths": [],
        "concerns": ["Empty submission"],
        "better_code": problem.get("reference"),
    }
