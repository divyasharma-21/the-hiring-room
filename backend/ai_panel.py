"""
Three-persona interview panel + deliberation + STAR + rewriter.
Uses Gemini when GEMINI_API_KEY is set; otherwise falls back to high-quality rule-based simulation
so the demo always works.
"""

from __future__ import annotations

import json
import re
import random
from collections import Counter
from typing import Any

from config import GEMINI_API_KEY, GEMINI_MODEL
from resume_analyzer import extract_skills

PERSONAS = {
    "hr": {
        "name": "HR",
        "title": "HR Partner",
        "focus": "culture fit, communication, collaboration, red flags, motivation",
        "color": "#7c3aed",
    },
    "tech_lead": {
        "name": "Tech Lead",
        "title": "Technical Lead",
        "focus": "technical depth, correctness, problem-solving, system design, failure modes",
        "color": "#2563eb",
    },
    "hiring_manager": {
        "name": "Hiring Manager",
        "title": "Hiring Manager",
        "focus": "impact, ownership, prioritization, team fit, business outcomes",
        "color": "#059669",
    },
}

# ---------- Gemini helper ----------

def _gemini_available() -> bool:
    return bool(GEMINI_API_KEY)


_genai_client = None


def _get_genai_client():
    """Lazily build one shared google-genai client (the old google-generativeai
    SDK is deprecated and its models, incl. gemini-2.0-flash, were shut down
    2026-06-01 — using it silently 404s and this whole app falls back to
    canned templates, which is exactly the 'feels rule-based' bug)."""
    global _genai_client
    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client


def _lang_instruction(language: str | None) -> str:
    """Append to system prompts so AI responds fully in the user's language."""
    if not language or language in ("en", "english", "English"):
        return " Respond entirely in English."
    names = {
        "hi": "Hindi",
        "kn": "Kannada",
        "hindi": "Hindi",
        "kannada": "Kannada",
    }
    name = names.get((language or "").lower(), language)
    return (
        f" CRITICAL: Respond entirely in {name}. Every sentence of your output must be in {name}. "
        f"Do not mix English except for unavoidable technical terms, code, or proper names."
    )


def _call_gemini(prompt: str, system: str = "", temperature: float = 0.7, language: str | None = None) -> str:
    if not _gemini_available():
        return ""
    try:
        from google.genai import types
        client = _get_genai_client()
        sys = system or ""
        if language:
            sys = (sys + _lang_instruction(language)).strip()
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=sys or None,
                max_output_tokens=2048,
            ),
        )
        text = getattr(resp, "text", None) or ""
        return text.strip()
    except Exception as e:
        print(f"[Gemini error] {type(e).__name__}: {e}")
        return ""


# ---------- Offline UI/content localization for AI fallbacks ----------
# Used when Gemini is unavailable so deliberation/mentor/resources still match the UI language.

_LOCALE = {
    "en": {
        "composite": "Composite panel view sits around {score} this round. ",
        "next_low": "Next step is a re-run with fuller answers.",
        "next_mid": "Next step should probe the weaker areas while keeping what worked.",
        "hr_strengths_mid": ["Reasonable communication", "No major red flags"],
        "hr_concerns_mid": ["Some answers stayed high-level"],
        "tech_strengths_mid": ["Some structured thinking"],
        "tech_concerns_mid": ["Limited discussion of failure modes", "Edge cases under-explored"],
        "hm_strengths_mid": ["Some ownership signal"],
        "hm_concerns_mid": ["Would still validate impact with concrete numbers"],
        "hr_strengths_high": ["Clear communication", "Collaborative framing", "No major red flags"],
        "tech_strengths_high": ["Structured thinking under pressure", "Relevant project experience"],
        "tech_concerns_high": ["Could still go deeper on edge cases"],
        "hm_strengths_high": ["Strong ownership signal", "Impact-oriented examples"],
        "hr_concerns_low": ["Answers too short to assess communication or culture fit"],
        "tech_concerns_low": ["No technical content to evaluate"],
        "hm_concerns_low": ["No ownership/impact evidence provided"],
        "follow_low": [
            "Walk us through one real example, start to finish — what was the situation, what did you do, and what happened?",
            "Pick your strongest project. What was your specific role, and what was the measurable outcome?",
            "Tell us about a time something you worked on didn't go as planned. What did you do next?",
        ],
        "follow_mid": [
            "Walk us through a production issue or bug you diagnosed and fixed end-to-end.",
            "Describe a technical trade-off you owned under deadline pressure — what did you optimize for?",
            "Tell us about a time stakeholder priorities conflicted with engineering quality. How did you navigate that?",
        ],
        "consensus_low_summary": "The panel did not see enough substantive answers this round to fairly evaluate the candidate — most responses were too short to show real Situation/Task/Action/Result content. This score reflects the lack of demonstrated content, not a judgment on the candidate's actual ability.",
        "consensus_low_disagreement": "There wasn't enough material for the panel to meaningfully disagree — the main gap was thin answers across the board.",
        "consensus_low_recommendation": "Re-run the interview and answer each question with a full example (a few sentences minimum) before the panel can give a real read.",
        "consensus_mid_summary": "The panel saw a mixed round — some reasonable signal on communication and ownership, with technical depth and result specificity being the main gaps to close.",
        "consensus_mid_disagreement": "Tech Lead wanted more depth on failure modes; Hiring Manager weighted the ownership signal more generously.",
        "consensus_mid_recommendation": "Advance to a focused follow-up round on technical depth and measurable outcomes, while reinforcing the communication strengths shown.",
        "consensus_high_summary": "The panel saw a strong, well-structured round with clear ownership, solid technical reasoning, and good communication throughout.",
        "consensus_high_disagreement": "Minor disagreement on how much further to probe technical edge cases, but all three leaned toward advancing.",
        "consensus_high_recommendation": "Advance to the next round; use a technical deep-dive to confirm depth on edge cases and scale.",
        "tier_low_hr": ["Honestly, I didn't get enough from the candidate to assess culture fit. Most answers were one-liners with no real story behind them.", "I can't call this a strong communication signal either way — there just wasn't enough substance in the responses to go on."],
        "tier_low_tech": ["There's no technical depth to evaluate here. The answers didn't get past a sentence, so I have nothing to sanity-check against the role.", "I'd normally probe failure modes and trade-offs, but the candidate didn't give us a real example to dig into."],
        "tier_low_hm": ["I don't see ownership or impact signal in what was submitted — the answers were too short to show any of that.", "From a hiring-manager lens, this session doesn't give me enough to recommend moving forward as-is."],
        "tier_mid_hr": ['Communication was okay — when they talked about "{snippet}", the framing was reasonable, though it stayed fairly high-level.', "Some good signal on collaboration, but a couple of answers could have gone deeper into how they actually handled friction."],
        "tier_mid_tech": ['Technical depth is there in places but inconsistent — the story around "{snippet}" had potential but skipped past the harder trade-offs.', "Decent structure, though I'd want a stronger example of debugging or a failure mode before I'm fully convinced."],
        "tier_mid_hm": ["Ownership signal is present but not fully proven yet — I'd want to see a clearer measurable outcome next round.", 'There\'s a reasonable impact story here, around "{snippet}", but it\'s more implied than demonstrated with numbers.'],
        "tier_high_hr": ['Strong communication throughout — the story about "{snippet}" showed real self-awareness and collaboration.', "Culture-fit signal is genuinely positive here; the candidate handled the conversation with clarity and confidence."],
        "tier_high_tech": ['Solid technical depth — "{snippet}" showed real ownership of a hard problem, including the trade-offs involved.', "This is one of the stronger technical stories I've heard this round; the reasoning held up under follow-up."],
        "tier_high_hm": ['Clear ownership and measurable impact in the "{snippet}" story — exactly the kind of signal this role needs.', "Strong impact orientation. I'd be comfortable moving this candidate forward on the strength of this round alone."],
        "mentor": "You showed up and practiced with a full panel — that alone is leadership. A clear strength is {strength}. A high-leverage growth area is {growth}. Next step: rehearse one story out loud using Situation → Action → Result, then re-run deliberation. You are building the skill, not waiting for permission.",
        "strength_default": "clear communication and willingness to practice under panel pressure",
        "growth_gap": "building evidence for {gap}",
        "growth_default": "tighter STAR endings with measurable results",
        "speaker_hr": "HR",
        "speaker_tech": "Tech Lead",
        "speaker_hm": "Hiring Manager",
        "resource_star": "Your answers often need a stronger {part} component in STAR stories.",
        "resource_star_default": "Strengthen structured behavioral answers (STAR).",
        "resource_gap": "Flagged as a gap vs the target job description ({skill}).",
        "resource_relevant": "Relevant to areas the panel or JD highlighted ({skill}).",
        "resource_general": "General interview preparation",
        "snippet_default": "their examples",
        "gemini_followups": [
            "Walk us through a production issue you diagnosed and fixed end-to-end.",
            "Describe a technical trade-off you owned under deadline pressure.",
            "How would you handle conflicting priorities between stakeholders and engineering quality?",
        ],
        "gemini_disagreement": "Panel members weighed technical depth and ownership differently.",
        "star_empty_notes": "Empty answer.",
        "star_empty_tip": "Start with context, state your responsibility, describe what you did, and end with the outcome.",
        "star_trivial_notes": "This is too short to be a real interview answer — there's no context, no action, and no result to evaluate.",
        "star_trivial_tip": "Give a full example: set the scene, say what you were responsible for, what you actually did, and what happened as a result.",
        "star_tip_situation": "Open with a short context: where you were and what was happening.",
        "star_tip_task": "State your specific responsibility or goal in one clear sentence.",
        "star_tip_action": "Describe what *you* did, step by step, with concrete verbs (built, fixed, led…).",
        "star_tip_result": "End with the outcome — ideally a measurable result or clear business/team impact.",
        "star_notes_strong": "Strong STAR structure — clear story with ownership and outcome.",
        "star_notes_partial": "Partial STAR structure. Strengthen the weaker parts for a complete interview story.",
        "star_notes_weak": "Answer is light on STAR structure. Add context, your role, concrete actions, and a clear result.",
        "star_tip_practice": "Keep practicing concise STAR stories for common behavioral themes.",
        "lead_tip_ownership": "Name one decision you owned — leadership shows up in choices, not only titles.",
        "lead_tip_collab": "Mention how you worked with others; panels listen for collaboration.",
        "lead_tip_impact": "Add a line on impact to others (team, users, or mentees) to surface leadership.",
        "conf_low": "Your content is a starting point — slow down, add one concrete action you took, and end with the result. Confidence grows when the story is complete.",
        "conf_result": "Strong start. Close with the outcome (metric, decision, or team impact) so the panel sees the finish line.",
        "conf_action": "Shift into first person: name 2–3 specific steps you took. Ownership language builds credibility.",
        "conf_high": "Solid STAR structure. Next time, tighten the opening context to one sentence so the impact lands faster.",
        "conf_default": "Lead with context in one line, then what you owned, then the result. That rhythm is what panels remember.",
        "imp_situation": "Added clearer context so the panel knows the setting.",
        "imp_task": "Made your responsibility / goal more explicit.",
        "imp_action": "Emphasized first-person actions (what you did).",
        "imp_result": "Brought the outcome into focus.",
        "imp_tightened": "Tightened wording and removed filler.",
        "imp_flow": "Improved flow toward a clearer Situation → Action → Result arc.",
        "imp_voice": "Kept your facts and voice — no invented achievements.",
        "coding_same_bug": "Submission still matches the buggy version",
        "coding_fixed": "Core bug appears fixed",
        "coding_matches": "Solution matches the intended behavior",
        "coding_key_fix": "Key fix pattern detected in your code",
        "coding_minor": "Minor structure/clarity differences from a production-ready fix",
        "coding_partial": "Fix is partial — some buggy patterns may remain",
        "coding_direction": "You moved in the right direction",
        "coding_unconfirmed": "Could not confirm the intended fix from the submission",
        "coding_structure": "Clear function structure",
        "coding_fb_good": "Tech Lead: Your fix for “{title}” addresses the failure mode. I can follow the change and would accept this in review with only nits, if any.",
        "coding_fb_partial": "Tech Lead: You identified the issue in “{title}”. Tighten edge handling and readability — see reference only if you want a cleaner shape.",
        "coding_fb_bad": "Tech Lead: “{title}” still looks incorrect or incomplete vs the reported bug. Re-read the failure mode and compare against the expected behavior.",
    },
    "hi": {
        "composite": "इस राउंड में पैनल का समग्र स्कोर लगभग {score} है। ",
        "next_low": "अगला कदम: अधिक विस्तृत उत्तरों के साथ इंटरव्यू फिर से दें।",
        "next_mid": "अगला कदम कमज़ोर क्षेत्रों को गहराई से जाँचना चाहिए, और जो अच्छा था उसे बनाए रखना चाहिए।",
        "hr_strengths_mid": ["उचित संचार", "कोई बड़ी रेड फ्लैग नहीं"],
        "hr_concerns_mid": ["कुछ उत्तर उच्च-स्तरीय रह गए"],
        "tech_strengths_mid": ["कुछ संरचित सोच"],
        "tech_concerns_mid": ["विफलता मोड पर सीमित चर्चा", "एज केस कम खोजे गए"],
        "hm_strengths_mid": ["कुछ स्वामित्व संकेत"],
        "hm_concerns_mid": ["ठोस संख्याओं से प्रभाव अभी भी सत्यापित करना होगा"],
        "hr_strengths_high": ["स्पष्ट संचार", "सहयोगी फ्रेमिंग", "कोई बड़ी रेड फ्लैग नहीं"],
        "tech_strengths_high": ["दबाव में संरचित सोच", "प्रासंगिक प्रोजेक्ट अनुभव"],
        "tech_concerns_high": ["एज केस पर और गहराई जा सकती है"],
        "hm_strengths_high": ["मज़बूत स्वामित्व संकेत", "प्रभाव-उन्मुख उदाहरण"],
        "hr_concerns_low": ["संचार या संस्कृति फिट आंकने के लिए उत्तर बहुत छोटे"],
        "tech_concerns_low": ["मूल्यांकन के लिए कोई तकनीकी सामग्री नहीं"],
        "hm_concerns_low": ["स्वामित्व/प्रभाव का कोई प्रमाण नहीं"],
        "follow_low": [
            "एक पूरा वास्तविक उदाहरण बताएँ — स्थिति क्या थी, आपने क्या किया, और क्या हुआ?",
            "अपना सबसे मज़बूत प्रोजेक्ट चुनें। आपकी विशिष्ट भूमिका क्या थी, और मापने योग्य परिणाम क्या था?",
            "किसी ऐसी चीज़ के बारे में बताएँ जो योजना के अनुसार नहीं गई। आपने आगे क्या किया?",
        ],
        "follow_mid": [
            "किसी प्रोडक्शन समस्या या बग के बारे में बताएँ जिसे आपने शुरू से अंत तक जाँचा और ठीक किया।",
            "समय की कमी में आपके द्वारा लिए गए एक तकनीकी ट्रेड-ऑफ का वर्णन करें — आपने किसके लिए अनुकूलित किया?",
            "जब हितधारक प्राथमिकताएँ इंजीनियरिंग गुणवत्ता से टकराईं, आपने कैसे निपटाया?",
        ],
        "consensus_low_summary": "पैनल को इस राउंड में उम्मीदवार का निष्पक्ष मूल्यांकन करने के लिए पर्याप्त ठोस उत्तर नहीं मिले — अधिकांश उत्तर बहुत छोटे थे। यह स्कोर प्रदर्शित सामग्री की कमी दर्शाता है, क्षमता का निर्णय नहीं।",
        "consensus_low_disagreement": "पैनल के लिए असहमति के लिए पर्याप्त सामग्री नहीं थी — मुख्य अंतर पतले उत्तर थे।",
        "consensus_low_recommendation": "इंटरव्यू फिर से दें और प्रत्येक प्रश्न का पूरा उदाहरण (कम से कम कुछ वाक्य) दें।",
        "consensus_mid_summary": "पैनल ने मिश्रित राउंड देखा — संचार और स्वामित्व पर कुछ उचित संकेत, तकनीकी गहराई और परिणाम की विशिष्टता मुख्य अंतर हैं।",
        "consensus_mid_disagreement": "टेक लीड विफलता मोड पर अधिक गहराई चाहते थे; हायरिंग मैनेजर ने स्वामित्व संकेत को अधिक उदारता से तौला।",
        "consensus_mid_recommendation": "तकनीकी गहराई और मापने योग्य परिणामों पर केंद्रित फॉलो-अप राउंड में आगे बढ़ें, और दिखाए गए संचार की ताकत को सुदृढ़ करें।",
        "consensus_high_summary": "पैनल ने मज़बूत, सुव्यवस्थित राउंड देखा — स्पष्ट स्वामित्व, ठोस तकनीकी तर्क और अच्छा संचार।",
        "consensus_high_disagreement": "तकनीकी एज केस पर कितनी और जाँच करें इस पर मामूली असहमति, लेकिन तीनों आगे बढ़ाने की ओर झुके।",
        "consensus_high_recommendation": "अगले राउंड में आगे बढ़ें; एज केस और स्केल पर गहराई की पुष्टि के लिए तकनीकी डीप-डाइव करें।",
        "tier_low_hr": ["ईमानदारी से, संस्कृति फिट आंकने के लिए पर्याप्त नहीं मिला। अधिकांश उत्तर एक-पंक्ति के थे।", "मज़बूत संचार संकेत नहीं कह सकता — उत्तरों में पर्याप्त सामग्री नहीं थी।"],
        "tier_low_tech": ["यहाँ मूल्यांकन करने लायक तकनीकी गहराई नहीं है। उत्तर एक वाक्य से आगे नहीं गए।", "आमतौर पर विफलता मोड पूछता हूँ, लेकिन उम्मीदवार ने कोई वास्तविक उदाहरण नहीं दिया।"],
        "tier_low_hm": ["प्रस्तुत उत्तरों में स्वामित्व या प्रभाव का संकेत नहीं दिखता — उत्तर बहुत छोटे थे।", "हायरिंग-मैनेजर नज़रिए से, आगे बढ़ाने के लिए पर्याप्त नहीं है।"],
        "tier_mid_hr": ['संचार ठीक था — जब उन्होंने "{snippet}" की बात की, फ्रेमिंग उचित थी, हालांकि उच्च-स्तरीय रही।', "सहयोग पर कुछ अच्छा संकेत, लेकिन कुछ उत्तरों में घर्षण संभालने की गहराई और हो सकती थी।"],
        "tier_mid_tech": ['तकनीकी गहराई कुछ जगह है लेकिन असंगत — "{snippet}" की कहानी में क्षमता थी लेकिन कठिन ट्रेड-ऑफ छोड़ दिए गए।', "उचित संरचना, हालांकि पूरी तरह आश्वस्त होने से पहले डिबगिंग या विफलता मोड का मज़बूत उदाहरण चाहूँगा।"],
        "tier_mid_hm": ["स्वामित्व संकेत मौजूद है लेकिन पूरी तरह सिद्ध नहीं — अगले राउंड में स्पष्ट मापने योग्य परिणाम चाहूँगा।", '"{snippet}" के आसपास उचित प्रभाव कहानी है, लेकिन संख्याओं से प्रदर्शित होने से अधिक निहित है।'],
        "tier_high_hr": ['पूरे राउंड में मज़बूत संचार — "{snippet}" की कहानी ने वास्तविक आत्म-जागरूकता और सहयोग दिखाया।', "संस्कृति-फिट संकेत वास्तव में सकारात्मक; उम्मीदवार ने स्पष्टता और आत्मविश्वास से बात की।"],
        "tier_high_tech": ['ठोस तकनीकी गहराई — "{snippet}" ने कठिन समस्या पर वास्तविक स्वामित्व दिखाया, ट्रेड-ऑफ सहित।', "इस राउंड की मज़बूत तकनीकी कहानियों में से एक; फॉलो-अप में तर्क टिका।"],
        "tier_high_hm": ['"{snippet}" कहानी में स्पष्ट स्वामित्व और मापने योग्य प्रभाव — ठीक वैसा संकेत जो इस भूमिका को चाहिए।', "मज़बूत प्रभाव अभिविन्यास। इस राउंड की ताकत पर आगे बढ़ाने में सहज हूँ।"],
        "mentor": "आपने पूरे पैनल के साथ अभ्यास किया — अकेले यही नेतृत्व है। एक स्पष्ट ताकत है {strength}। उच्च-लाभ वाला विकास क्षेत्र है {growth}। अगला कदम: Situation → Action → Result का उपयोग करके एक कहानी ज़ोर से अभ्यास करें, फिर विचार-विमर्श फिर चलाएँ। आप कौशल बना रहे हैं, अनुमति की प्रतीक्षा नहीं कर रहे।",
        "strength_default": "स्पष्ट संचार और पैनल दबाव में अभ्यास करने की इच्छा",
        "growth_gap": "{gap} के लिए साक्ष्य बनाना",
        "growth_default": "मापने योग्य परिणामों के साथ tighter STAR अंत",
        "speaker_hr": "HR",
        "speaker_tech": "टेक लीड",
        "speaker_hm": "हायरिंग मैनेजर",
        "resource_star": "आपके उत्तरों में STAR कहानियों के {part} भाग को अक्सर मज़बूत करने की आवश्यकता होती है।",
        "resource_star_default": "संरचित व्यवहारिक उत्तर (STAR) मज़बूत करें।",
        "resource_gap": "लक्ष्य जॉब डिस्क्रिप्शन के मुकाबले अंतर के रूप में चिह्नित ({skill})।",
        "resource_relevant": "पैनल या JD द्वारा हाइलाइट किए गए क्षेत्रों से संबंधित ({skill})।",
        "resource_general": "सामान्य इंटरव्यू तैयारी",
        "snippet_default": "उनके उदाहरण",
        "gemini_followups": [
            "किसी प्रोडक्शन समस्या के बारे में बताएँ जिसे आपने शुरू से अंत तक जाँचा और ठीक किया।",
            "समय की कमी में आपके द्वारा लिए गए एक तकनीकी ट्रेड-ऑफ का वर्णन करें।",
            "हितधारक प्राथमिकताएँ और इंजीनियरिंग गुणवत्ता टकराने पर आप कैसे निपटते?",
        ],
        "gemini_disagreement": "पैनल सदस्यों ने तकनीकी गहराई और स्वामित्व को अलग-अलग तौला।",
        "star_empty_notes": "खाली जवाब।",
        "star_empty_tip": "संदर्भ से शुरू करें, अपनी जिम्मेदारी बताएँ, आपने क्या किया वर्णन करें, और परिणाम पर समाप्त करें।",
        "star_trivial_notes": "यह वास्तविक इंटरव्यू जवाब के लिए बहुत छोटा है — कोई संदर्भ, कोई कार्रवाई, कोई परिणाम नहीं।",
        "star_trivial_tip": "पूरा उदाहरण दें: दृश्य सेट करें, जिम्मेदारी बताएँ, आपने वास्तव में क्या किया, और परिणाम क्या हुआ।",
        "star_tip_situation": "छोटे संदर्भ से शुरू करें: आप कहाँ थे और क्या हो रहा था।",
        "star_tip_task": "अपनी विशिष्ट जिम्मेदारी या लक्ष्य एक स्पष्ट वाक्य में बताएँ।",
        "star_tip_action": "आपने *क्या* किया, कदम-दर-कदम, ठोस क्रियाओं के साथ (बनाया, ठीक किया, नेतृत्व किया…)।",
        "star_tip_result": "परिणाम पर समाप्त करें — आदर्श रूप से मापने योग्य परिणाम या स्पष्ट व्यावसायिक/टीम प्रभाव।",
        "star_notes_strong": "मज़बूत STAR संरचना — स्पष्ट कहानी, स्वामित्व और परिणाम के साथ।",
        "star_notes_partial": "आंशिक STAR संरचना। पूरी इंटरव्यू कहानी के लिए कमज़ोर भागों को मज़बूत करें।",
        "star_notes_weak": "जवाब में STAR संरचना कमज़ोर है। संदर्भ, भूमिका, ठोस कार्रवाई और स्पष्ट परिणाम जोड़ें।",
        "star_tip_practice": "सामान्य व्यवहारिक विषयों के लिए संक्षिप्त STAR कहानियों का अभ्यास जारी रखें।",
        "lead_tip_ownership": "एक निर्णय बताएँ जिसका आपने स्वामित्व लिया — नेतृत्व विकल्पों में दिखता है, केवल पदों में नहीं।",
        "lead_tip_collab": "दूसरों के साथ कैसे काम किया उल्लेख करें; पैनल सहयोग सुनता है।",
        "lead_tip_impact": "दूसरों (टीम, उपयोगकर्ता, मेंटी) पर प्रभाव की एक पंक्ति जोड़ें ताकि नेतृत्व सामने आए।",
        "conf_low": "आपकी सामग्री एक शुरुआत है — धीरे बोलें, एक ठोस कार्रवाई जोड़ें, और परिणाम पर समाप्त करें। कहानी पूरी होने पर आत्मविश्वास बढ़ता है।",
        "conf_result": "मज़बूत शुरुआत। परिणाम (मीट्रिक, निर्णय, या टीम प्रभाव) के साथ बंद करें ताकि पैनल अंत देखे।",
        "conf_action": "प्रथम पुरुष में आएँ: 2–3 विशिष्ट कदम बताएँ जो आपने लिए। स्वामित्व की भाषा विश्वसनीयता बनाती है।",
        "conf_high": "ठोस STAR संरचना। अगली बार शुरुआती संदर्भ को एक वाक्य में बाँधें ताकि प्रभाव जल्दी पहुँचे।",
        "conf_default": "एक पंक्ति में संदर्भ, फिर आपने क्या स्वामित्व लिया, फिर परिणाम। यही लय पैनल याद रखता है।",
        "imp_situation": "पैनल को सेटिंग पता चले, इसके लिए स्पष्ट संदर्भ जोड़ा गया।",
        "imp_task": "आपकी जिम्मेदारी / लक्ष्य को अधिक स्पष्ट किया गया।",
        "imp_action": "प्रथम-पुरुष कार्रवाइयों पर ज़ोर (आपने क्या किया)।",
        "imp_result": "परिणाम को केंद्र में लाया गया।",
        "imp_tightened": "शब्दावली कसी गई और भराव हटाया गया।",
        "imp_flow": "Situation → Action → Result की ओर स्पष्ट प्रवाह।",
        "imp_voice": "आपके तथ्य और आवाज़ रखी गई — कोई काल्पनिक उपलब्धि नहीं।",
        "coding_same_bug": "सबमिशन अभी भी बगी संस्करण से मेल खाता है",
        "coding_fixed": "मुख्य बग ठीक लगता है",
        "coding_matches": "समाधान अपेक्षित व्यवहार से मेल खाता है",
        "coding_key_fix": "आपके कोड में मुख्य फिक्स पैटर्न मिला",
        "coding_minor": "प्रोडक्शन-रेडी फिक्स से मामूली संरचना/स्पष्टता अंतर",
        "coding_partial": "फिक्स आंशिक — कुछ बगी पैटर्न रह सकते हैं",
        "coding_direction": "आप सही दिशा में बढ़े",
        "coding_unconfirmed": "सबमिशन से अपेक्षित फिक्स की पुष्टि नहीं हो सकी",
        "coding_structure": "स्पष्ट फ़ंक्शन संरचना",
        "coding_fb_good": "टेक लीड: “{title}” का आपका फिक्स विफलता मोड को संबोधित करता है। परिवर्तन समझ में आता है और समीक्षा में स्वीकार्य होगा।",
        "coding_fb_partial": "टेक लीड: आपने “{title}” में समस्या पहचानी। एज हैंडलिंग और पठनीयता कसें — साफ़ आकार के लिए संदर्भ देखें।",
        "coding_fb_bad": "टेक लीड: “{title}” अभी भी गलत या अधूरा लगता है। विफलता मोड फिर पढ़ें और अपेक्षित व्यवहार से तुलना करें।",
    },
    "kn": {
        "composite": "ಈ ಸುತ್ತಿನಲ್ಲಿ ಪ್ಯಾನಲ್‌ನ ಒಟ್ಟು ಸ್ಕೋರ್ ಸುಮಾರು {score}. ",
        "next_low": "ಮುಂದಿನ ಹೆಜ್ಜೆ: ಹೆಚ್ಚು ವಿವರವಾದ ಉತ್ತರಗಳೊಂದಿಗೆ ಸಂದರ್ಶನವನ್ನು ಮತ್ತೆ ನಡೆಸಿ.",
        "next_mid": "ಮುಂದಿನ ಹೆಜ್ಜೆ ದುರ್ಬಲ ಪ್ರದೇಶಗಳನ್ನು ಆಳವಾಗಿ ಪರಿಶೀಲಿಸಬೇಕು, ಚೆನ್ನಾಗಿದ್ದನ್ನು ಉಳಿಸಿಕೊಳ್ಳಬೇಕು.",
        "hr_strengths_mid": ["ಸಮಂಜಸ ಸಂವಹನ", "ದೊಡ್ಡ ಕೆಂಪು ಧ್ವಜಗಳಿಲ್ಲ"],
        "hr_concerns_mid": ["ಕೆಲವು ಉತ್ತರಗಳು ಉನ್ನತ-ಮಟ್ಟದಲ್ಲೇ ಉಳಿದವು"],
        "tech_strengths_mid": ["ಕೆಲವು ರಚನಾತ್ಮಕ ಚಿಂತನೆ"],
        "tech_concerns_mid": ["ವೈಫಲ್ಯ ಮೋಡ್‌ಗಳ ಬಗ್ಗೆ ಸೀಮಿತ ಚರ್ಚೆ", "ಎಡ್ಜ್ ಕೇಸ್‌ಗಳು ಕಡಿಮೆ ಅನ್ವೇಷಿತ"],
        "hm_strengths_mid": ["ಕೆಲವು ಮಾಲೀಕತ್ವ ಸಂಕೇತ"],
        "hm_concerns_mid": ["ಕಾಂಕ್ರೀಟ್ ಸಂಖ್ಯೆಗಳಿಂದ ಪ್ರಭಾವವನ್ನು ಇನ್ನೂ ಪರಿಶೀಲಿಸಬೇಕು"],
        "hr_strengths_high": ["ಸ್ಪಷ್ಟ ಸಂವಹನ", "ಸಹಕಾರಿ ಫ್ರೇಮಿಂಗ್", "ದೊಡ್ಡ ಕೆಂಪು ಧ್ವಜಗಳಿಲ್ಲ"],
        "tech_strengths_high": ["ಒತ್ತಡದಲ್ಲಿ ರಚನಾತ್ಮಕ ಚಿಂತನೆ", "ಸಂಬಂಧಿತ ಪ್ರಾಜೆಕ್ಟ್ ಅನುಭವ"],
        "tech_concerns_high": ["ಎಡ್ಜ್ ಕೇಸ್‌ಗಳಲ್ಲಿ ಇನ್ನೂ ಆಳಕ್ಕೆ ಹೋಗಬಹುದು"],
        "hm_strengths_high": ["ಬಲವಾದ ಮಾಲೀಕತ್ವ ಸಂಕೇತ", "ಪ್ರಭಾವ-ಕೇಂದ್ರಿತ ಉದಾಹರಣೆಗಳು"],
        "hr_concerns_low": ["ಸಂವಹನ ಅಥವಾ ಸಂಸ್ಕೃತಿ ಹೊಂದಾಣಿಕೆ ನಿರ್ಣಯಿಸಲು ಉತ್ತರಗಳು ತುಂಬಾ ಚಿಕ್ಕವು"],
        "tech_concerns_low": ["ಮೌಲ್ಯಮಾಪನಕ್ಕೆ ತಾಂತ್ರಿಕ ವಿಷಯವಿಲ್ಲ"],
        "hm_concerns_low": ["ಮಾಲೀಕತ್ವ/ಪ್ರಭಾವದ ಪುರಾವೆ ಇಲ್ಲ"],
        "follow_low": [
            "ಒಂದು ಸಂಪೂರ್ಣ ನೈಜ ಉದಾಹರಣೆ ಹೇಳಿ — ಪರಿಸ್ಥಿತಿ ಏನು, ನೀವು ಏನು ಮಾಡಿದಿರಿ, ಏನಾಯಿತು?",
            "ನಿಮ್ಮ ಬಲವಾದ ಪ್ರಾಜೆಕ್ಟ್ ಆಯ್ಕೆಮಾಡಿ. ನಿಮ್ಮ ನಿರ್ದಿಷ್ಟ ಪಾತ್ರ ಏನು, ಅಳೆಯಬಹುದಾದ ಫಲಿತಾಂಶ ಏನು?",
            "ಯೋಜನೆಯಂತೆ ನಡೆಯದ ಯಾವುದಾದರೂ ಬಗ್ಗೆ ಹೇಳಿ. ನೀವು ನಂತರ ಏನು ಮಾಡಿದಿರಿ?",
        ],
        "follow_mid": [
            "ನೀವು ಆರಂಭದಿಂದ ಅಂತ್ಯದವರೆಗೆ ಪತ್ತೆಹಚ್ಚಿ ಸರಿಪಡಿಸಿದ ಪ್ರೊಡಕ್ಷನ್ ಸಮಸ್ಯೆ ಅಥವಾ ಬಗ್ ಬಗ್ಗೆ ಹೇಳಿ.",
            "ಡೆಡ್‌ಲೈನ್ ಒತ್ತಡದಲ್ಲಿ ನೀವು ತೆಗೆದುಕೊಂಡ ತಾಂತ್ರಿಕ ಟ್ರೇಡ್-ಆಫ್ ವಿವರಿಸಿ — ಯಾವುದಕ್ಕಾಗಿ ಆಪ್ಟಿಮೈಜ್ ಮಾಡಿದಿರಿ?",
            "ಹಿತಾಸಕ್ತಿ ಪಕ್ಷಗಳ ಆದ್ಯತೆಗಳು ಎಂಜಿನಿಯರಿಂಗ್ ಗುಣಮಟ್ಟದೊಂದಿಗೆ ಘರ್ಷಣೆಯಾದಾಗ ನೀವು ಹೇಗೆ ನಿರ್ವಹಿಸಿದಿರಿ?",
        ],
        "consensus_low_summary": "ಪ್ಯಾನಲ್‌ಗೆ ಈ ಸುತ್ತಿನಲ್ಲಿ ಅಭ್ಯರ್ಥಿಯನ್ನು ನ್ಯಾಯಯುತವಾಗಿ ಮೌಲ್ಯಮಾಪನ ಮಾಡಲು ಸಾಕಷ್ಟು ವಸ್ತುನಿಷ್ಠ ಉತ್ತರಗಳು ಸಿಗಲಿಲ್ಲ — ಬಹುಪಾಲು ಉತ್ತರಗಳು ತುಂಬಾ ಚಿಕ್ಕವು. ಈ ಸ್ಕೋರ್ ಪ್ರದರ್ಶಿತ ವಿಷಯದ ಕೊರತೆಯನ್ನು ಪ್ರತಿಬಿಂಬಿಸುತ್ತದೆ, ಸಾಮರ್ಥ್ಯದ ತೀರ್ಪಲ್ಲ.",
        "consensus_low_disagreement": "ಪ್ಯಾನಲ್‌ಗೆ ಅರ್ಥಪೂರ್ಣವಾಗಿ ಭಿನ್ನಾಭಿಪ್ರಾಯ ಹೊಂದಲು ಸಾಕಷ್ಟು ವಸ್ತು ಇರಲಿಲ್ಲ — ಮುಖ್ಯ ಅಂತರ ತೆಳುವಾದ ಉತ್ತರಗಳು.",
        "consensus_low_recommendation": "ಸಂದರ್ಶನವನ್ನು ಮತ್ತೆ ನಡೆಸಿ ಮತ್ತು ಪ್ರತಿ ಪ್ರಶ್ನೆಗೆ ಪೂರ್ಣ ಉದಾಹರಣೆ (ಕನಿಷ್ಠ ಕೆಲವು ವಾಕ್ಯಗಳು) ನೀಡಿ.",
        "consensus_mid_summary": "ಪ್ಯಾನಲ್ ಮಿಶ್ರ ಸುತ್ತನ್ನು ನೋಡಿತು — ಸಂವಹನ ಮತ್ತು ಮಾಲೀಕತ್ವದಲ್ಲಿ ಕೆಲವು ಸಮಂಜಸ ಸಂಕೇತ, ತಾಂತ್ರಿಕ ಆಳ ಮತ್ತು ಫಲಿತಾಂಶದ ನಿರ್ದಿಷ್ಟತೆ ಮುಖ್ಯ ಅಂತರಗಳು.",
        "consensus_mid_disagreement": "ಟೆಕ್ ಲೀಡ್ ವೈಫಲ್ಯ ಮೋಡ್‌ಗಳಲ್ಲಿ ಹೆಚ್ಚು ಆಳ ಬಯಸಿದರು; ಹೈರಿಂಗ್ ಮ್ಯಾನೇಜರ್ ಮಾಲೀಕತ್ವ ಸಂಕೇತವನ್ನು ಹೆಚ್ಚು ಉದಾರವಾಗಿ ತೂಗಿದರು.",
        "consensus_mid_recommendation": "ತಾಂತ್ರಿಕ ಆಳ ಮತ್ತು ಅಳೆಯಬಹುದಾದ ಫಲಿತಾಂಶಗಳ ಮೇಲೆ ಕೇಂದ್ರೀಕೃತ ಅನುಸರಣಾ ಸುತ್ತಿಗೆ ಮುಂದುವರಿಸಿ, ತೋರಿಸಿದ ಸಂವಹನ ಶಕ್ತಿಗಳನ್ನು ಬಲಪಡಿಸಿ.",
        "consensus_high_summary": "ಪ್ಯಾನಲ್ ಬಲವಾದ, ಚೆನ್ನಾಗಿ ರಚಿತ ಸುತ್ತನ್ನು ನೋಡಿತು — ಸ್ಪಷ್ಟ ಮಾಲೀಕತ್ವ, ಘನ ತಾಂತ್ರಿಕ ತರ್ಕ ಮತ್ತು ಉತ್ತಮ ಸಂವಹನ.",
        "consensus_high_disagreement": "ತಾಂತ್ರಿಕ ಎಡ್ಜ್ ಕೇಸ್‌ಗಳನ್ನು ಎಷ್ಟು ಮುಂದುವರಿಸಬೇಕು ಎಂಬುದರಲ್ಲಿ ಸಣ್ಣ ಭಿನ್ನಾಭಿಪ್ರಾಯ, ಆದರೆ ಮೂವರೂ ಮುಂದುವರಿಸುವತ್ತ ಒಲವು.",
        "consensus_high_recommendation": "ಮುಂದಿನ ಸುತ್ತಿಗೆ ಮುಂದುವರಿಸಿ; ಎಡ್ಜ್ ಕೇಸ್ ಮತ್ತು ಸ್ಕೇಲ್‌ನಲ್ಲಿ ಆಳ ದೃಢಪಡಿಸಲು ತಾಂತ್ರಿಕ ಡೀಪ್-ಡೈವ್ ಬಳಸಿ.",
        "tier_low_hr": ["ನಿಜವಾಗಿಯೂ, ಸಂಸ್ಕೃತಿ ಹೊಂದಾಣಿಕೆ ನಿರ್ಣಯಿಸಲು ಸಾಕಷ್ಟು ಸಿಗಲಿಲ್ಲ. ಬಹುಪಾಲು ಉತ್ತರಗಳು ಒಂದು ಸಾಲಿನವು.", "ಬಲವಾದ ಸಂವಹನ ಸಂಕೇತ ಎನ್ನಲಾಗುವುದಿಲ್ಲ — ಉತ್ತರಗಳಲ್ಲಿ ಸಾಕಷ್ಟು ವಸ್ತು ಇರಲಿಲ್ಲ."],
        "tier_low_tech": ["ಇಲ್ಲಿ ಮೌಲ್ಯಮಾಪನ ಮಾಡುವ ತಾಂತ್ರಿಕ ಆಳವಿಲ್ಲ. ಉತ್ತರಗಳು ಒಂದು ವಾಕ್ಯವನ್ನು ದಾಟಲಿಲ್ಲ.", "ಸಾಮಾನ್ಯವಾಗಿ ವೈಫಲ್ಯ ಮೋಡ್‌ಗಳನ್ನು ಪರಿಶೀಲಿಸುತ್ತೇನೆ, ಆದರೆ ಅಭ್ಯರ್ಥಿ ನಿಜವಾದ ಉದಾಹರಣೆ ನೀಡಲಿಲ್ಲ."],
        "tier_low_hm": ["ಸಲ್ಲಿಸಿದ ಉತ್ತರಗಳಲ್ಲಿ ಮಾಲೀಕತ್ವ ಅಥವಾ ಪ್ರಭಾವ ಸಂಕೇತ ಕಾಣುವುದಿಲ್ಲ — ಉತ್ತರಗಳು ತುಂಬಾ ಚಿಕ್ಕವು.", "ಹೈರಿಂಗ್-ಮ್ಯಾನೇಜರ್ ದೃಷ್ಟಿಕೋನದಿಂದ, ಮುಂದುವರಿಸಲು ಸಾಕಷ್ಟಿಲ್ಲ."],
        "tier_mid_hr": ['ಸಂವಹನ ಸರಿಯಾಗಿತ್ತು — ಅವರು "{snippet}" ಬಗ್ಗೆ ಮಾತನಾಡಿದಾಗ ಫ್ರೇಮಿಂಗ್ ಸಮಂಜಸವಾಗಿತ್ತು, ಆದರೆ ಉನ್ನತ-ಮಟ್ಟದಲ್ಲೇ ಉಳಿಯಿತು.', "ಸಹಕಾರದಲ್ಲಿ ಕೆಲವು ಉತ್ತಮ ಸಂಕೇತ, ಆದರೆ ಕೆಲವು ಉತ್ತರಗಳಲ್ಲಿ ಘರ್ಷಣೆ ನಿರ್ವಹಣೆಯ ಆಳ ಹೆಚ್ಚಾಗಬಹುದಿತ್ತು."],
        "tier_mid_tech": ['ತಾಂತ್ರಿಕ ಆಳ ಕೆಲವು ಕಡೆ ಇದೆ ಆದರೆ ಅಸಮಂಜಸ — "{snippet}" ಕಥೆಯಲ್ಲಿ ಸಾಮರ್ಥ್ಯವಿತ್ತು ಆದರೆ ಕಠಿಣ ಟ್ರೇಡ್-ಆಫ್‌ಗಳನ್ನು ಬಿಟ್ಟುಬಿಡಲಾಯಿತು.', "ಸಮಂಜಸ ರಚನೆ, ಆದರೆ ಸಂಪೂರ್ಣವಾಗಿ ಮನವರಿಕೆಯಾಗುವ ಮೊದಲು ಡೀಬಗ್ಗಿಂಗ್ ಅಥವಾ ವೈಫಲ್ಯ ಮೋಡ್‌ನ ಬಲವಾದ ಉದಾಹರಣೆ ಬೇಕು."],
        "tier_mid_hm": ["ಮಾಲೀಕತ್ವ ಸಂಕೇತ ಇದೆ ಆದರೆ ಸಂಪೂರ್ಣವಾಗಿ ಸಾಬೀತಾಗಿಲ್ಲ — ಮುಂದಿನ ಸುತ್ತಿನಲ್ಲಿ ಸ್ಪಷ್ಟ ಅಳೆಯಬಹುದಾದ ಫಲಿತಾಂಶ ಬೇಕು.", '"{snippet}" ಸುತ್ತ ಸಮಂಜಸ ಪ್ರಭಾವ ಕಥೆ ಇದೆ, ಆದರೆ ಸಂಖ್ಯೆಗಳಿಂದ ತೋರಿಸುವುದಕ್ಕಿಂತ ಹೆಚ್ಚು ಸೂಚಿತವಾಗಿದೆ.'],
        "tier_high_hr": ['ಪೂರ್ಣ ಸುತ್ತಿನಲ್ಲಿ ಬಲವಾದ ಸಂವಹನ — "{snippet}" ಕಥೆ ನಿಜವಾದ ಸ್ವಯಂ-ಜಾಗೃತಿ ಮತ್ತು ಸಹಕಾರವನ್ನು ತೋರಿಸಿತು.', "ಸಂಸ್ಕೃತಿ-ಹೊಂದಾಣಿಕೆ ಸಂಕೇತ ನಿಜವಾಗಿಯೂ ಧನಾತ್ಮಕ; ಅಭ್ಯರ್ಥಿ ಸ್ಪಷ್ಟತೆ ಮತ್ತು ಆತ್ಮವಿಶ್ವಾಸದಿಂದ ಮಾತನಾಡಿದರು."],
        "tier_high_tech": ['ಘನ ತಾಂತ್ರಿಕ ಆಳ — "{snippet}" ಕಠಿಣ ಸಮಸ್ಯೆಯ ಮೇಲೆ ನಿಜವಾದ ಮಾಲೀಕತ್ವವನ್ನು ತೋರಿಸಿತು, ಟ್ರೇಡ್-ಆಫ್‌ಗಳೊಂದಿಗೆ.', "ಈ ಸುತ್ತಿನ ಬಲವಾದ ತಾಂತ್ರಿಕ ಕಥೆಗಳಲ್ಲಿ ಒಂದು; ಅನುಸರಣೆಯಲ್ಲಿ ತರ್ಕ ನಿಂತಿತು."],
        "tier_high_hm": ['"{snippet}" ಕಥೆಯಲ್ಲಿ ಸ್ಪಷ್ಟ ಮಾಲೀಕತ್ವ ಮತ್ತು ಅಳೆಯಬಹುದಾದ ಪ್ರಭಾವ — ಈ ಪಾತ್ರಕ್ಕೆ ಬೇಕಾದ ಸಂಕೇತ.', "ಬಲವಾದ ಪ್ರಭಾವ ದೃಷ್ಟಿಕೋನ. ಈ ಸುತ್ತಿನ ಬಲದ ಮೇಲೆ ಮುಂದುವರಿಸಲು ಆರಾಮದಾಯಕ."],
        "mentor": "ನೀವು ಪೂರ್ಣ ಪ್ಯಾನಲ್‌ನೊಂದಿಗೆ ಅಭ್ಯಾಸ ಮಾಡಿದಿರಿ — ಅದು ಮಾತ್ರ ನಾಯಕತ್ವ. ಸ್ಪಷ್ಟ ಶಕ್ತಿ {strength}. ಹೆಚ್ಚು ಲಾಭದಾಯಕ ಬೆಳವಣಿಗೆ ಪ್ರದೇಶ {growth}. ಮುಂದಿನ ಹೆಜ್ಜೆ: Situation → Action → Result ಬಳಸಿ ಒಂದು ಕಥೆಯನ್ನು ಗಟ್ಟಿಯಾಗಿ ಅಭ್ಯಾಸ ಮಾಡಿ, ನಂತರ ಚರ್ಚೆಯನ್ನು ಮತ್ತೆ ನಡೆಸಿ. ನೀವು ಕೌಶಲ್ಯವನ್ನು ನಿರ್ಮಿಸುತ್ತಿದ್ದೀರಿ, ಅನುಮತಿಗಾಗಿ ಕಾಯುತ್ತಿಲ್ಲ.",
        "strength_default": "ಸ್ಪಷ್ಟ ಸಂವಹನ ಮತ್ತು ಪ್ಯಾನಲ್ ಒತ್ತಡದಲ್ಲಿ ಅಭ್ಯಾಸ ಮಾಡುವ ಇಚ್ಛೆ",
        "growth_gap": "{gap} ಗಾಗಿ ಪುರಾವೆ ನಿರ್ಮಿಸುವುದು",
        "growth_default": "ಅಳೆಯಬಹುದಾದ ಫಲಿತಾಂಶಗಳೊಂದಿಗೆ ಬಿಗಿಯಾದ STAR ಅಂತ್ಯಗಳು",
        "speaker_hr": "HR",
        "speaker_tech": "ಟೆಕ್ ಲೀಡ್",
        "speaker_hm": "ಹೈರಿಂಗ್ ಮ್ಯಾನೇಜರ್",
        "resource_star": "ನಿಮ್ಮ ಉತ್ತರಗಳಲ್ಲಿ STAR ಕಥೆಗಳ {part} ಭಾಗವನ್ನು ಆಗಾಗ್ಗೆ ಬಲಪಡಿಸಬೇಕಾಗುತ್ತದೆ.",
        "resource_star_default": "ರಚನಾತ್ಮಕ ವರ್ತನೆಯ ಉತ್ತರಗಳನ್ನು (STAR) ಬಲಪಡಿಸಿ.",
        "resource_gap": "ಗುರಿ ಉದ್ಯೋಗ ವಿವರಣೆಗೆ ಹೋಲಿಸಿದರೆ ಅಂತರವೆಂದು ಗುರುತಿಸಲಾಗಿದೆ ({skill}).",
        "resource_relevant": "ಪ್ಯಾನಲ್ ಅಥವಾ JD ಹೈಲೈಟ್ ಮಾಡಿದ ಪ್ರದೇಶಗಳಿಗೆ ಸಂಬಂಧಿಸಿದೆ ({skill}).",
        "resource_general": "ಸಾಮಾನ್ಯ ಸಂದರ್ಶನ ತಯಾರಿ",
        "snippet_default": "ಅವರ ಉದಾಹರಣೆಗಳು",
        "gemini_followups": [
            "ನೀವು ಆರಂಭದಿಂದ ಅಂತ್ಯದವರೆಗೆ ಪತ್ತೆಹಚ್ಚಿ ಸರಿಪಡಿಸಿದ ಪ್ರೊಡಕ್ಷನ್ ಸಮಸ್ಯೆ ಬಗ್ಗೆ ಹೇಳಿ.",
            "ಡೆಡ್‌ಲೈನ್ ಒತ್ತಡದಲ್ಲಿ ನೀವು ತೆಗೆದುಕೊಂಡ ತಾಂತ್ರಿಕ ಟ್ರೇಡ್-ಆಫ್ ವಿವರಿಸಿ.",
            "ಹಿತಾಸಕ್ತಿ ಪಕ್ಷಗಳ ಆದ್ಯತೆಗಳು ಮತ್ತು ಎಂಜಿನಿಯರಿಂಗ್ ಗುಣಮಟ್ಟ ಘರ್ಷಣೆಯಾದಾಗ ನೀವು ಹೇಗೆ ನಿರ್ವಹಿಸುತ್ತೀರಿ?",
        ],
        "gemini_disagreement": "ಪ್ಯಾನಲ್ ಸದಸ್ಯರು ತಾಂತ್ರಿಕ ಆಳ ಮತ್ತು ಮಾಲೀಕತ್ವವನ್ನು ವಿಭಿನ್ನವಾಗಿ ತೂಗಿದರು.",
        "star_empty_notes": "ಖಾಲಿ ಉತ್ತರ.",
        "star_empty_tip": "ಸನ್ನಿವೇಶದಿಂದ ಪ್ರಾರಂಭಿಸಿ, ನಿಮ್ಮ ಜವಾಬ್ದಾರಿ ಹೇಳಿ, ನೀವು ಏನು ಮಾಡಿದಿರಿ ವಿವರಿಸಿ, ಫಲಿತಾಂಶದೊಂದಿಗೆ ಮುಗಿಸಿ.",
        "star_trivial_notes": "ಇದು ನಿಜವಾದ ಸಂದರ್ಶನ ಉತ್ತರಕ್ಕೆ ತುಂಬಾ ಚಿಕ್ಕದು — ಸನ್ನಿವೇಶ, ಕ್ರಿಯೆ ಅಥವಾ ಫಲಿತಾಂಶವಿಲ್ಲ.",
        "star_trivial_tip": "ಪೂರ್ಣ ಉದಾಹರಣೆ ನೀಡಿ: ದೃಶ್ಯ ಹೊಂದಿಸಿ, ಜವಾಬ್ದಾರಿ ಹೇಳಿ, ನೀವು ನಿಜವಾಗಿ ಏನು ಮಾಡಿದಿರಿ, ಫಲಿತಾಂಶ ಏನಾಯಿತು.",
        "star_tip_situation": "ಚಿಕ್ಕ ಸನ್ನಿವೇಶದಿಂದ ಪ್ರಾರಂಭಿಸಿ: ನೀವು ಎಲ್ಲಿದ್ದಿರಿ ಮತ್ತು ಏನಾಗುತ್ತಿತ್ತು.",
        "star_tip_task": "ನಿಮ್ಮ ನಿರ್ದಿಷ್ಟ ಜವಾಬ್ದಾರಿ ಅಥವಾ ಗುರಿಯನ್ನು ಒಂದು ಸ್ಪಷ್ಟ ವಾಕ್ಯದಲ್ಲಿ ಹೇಳಿ.",
        "star_tip_action": "ನೀವು *ಏನು* ಮಾಡಿದಿರಿ, ಹಂತ ಹಂತವಾಗಿ, ಕಾಂಕ್ರೀಟ್ ಕ್ರಿಯಾಪದಗಳೊಂದಿಗೆ (ನಿರ್ಮಿಸಿದೆ, ಸರಿಪಡಿಸಿದೆ, ನಾಯಕತ್ವ…).",
        "star_tip_result": "ಫಲಿತಾಂಶದೊಂದಿಗೆ ಮುಗಿಸಿ — ಆದರ್ಶವಾಗಿ ಅಳೆಯಬಹುದಾದ ಫಲಿತಾಂಶ ಅಥವಾ ಸ್ಪಷ್ಟ ವ್ಯವಹಾರ/ತಂಡ ಪ್ರಭಾವ.",
        "star_notes_strong": "ಬಲವಾದ STAR ರಚನೆ — ಸ್ಪಷ್ಟ ಕಥೆ, ಮಾಲೀಕತ್ವ ಮತ್ತು ಫಲಿತಾಂಶದೊಂದಿಗೆ.",
        "star_notes_partial": "ಭಾಗಶಃ STAR ರಚನೆ. ಪೂರ್ಣ ಸಂದರ್ಶನ ಕಥೆಗೆ ದುರ್ಬಲ ಭಾಗಗಳನ್ನು ಬಲಪಡಿಸಿ.",
        "star_notes_weak": "ಉತ್ತರದಲ್ಲಿ STAR ರಚನೆ ದುರ್ಬಲ. ಸನ್ನಿವೇಶ, ಪಾತ್ರ, ಕಾಂಕ್ರೀಟ್ ಕ್ರಿಯೆಗಳು ಮತ್ತು ಸ್ಪಷ್ಟ ಫಲಿತಾಂಶ ಸೇರಿಸಿ.",
        "star_tip_practice": "ಸಾಮಾನ್ಯ ವರ್ತನೆಯ ವಿಷಯಗಳಿಗೆ ಸಂಕ್ಷಿಪ್ತ STAR ಕಥೆಗಳನ್ನು ಅಭ್ಯಾಸ ಮಾಡುತ್ತಿರಿ.",
        "lead_tip_ownership": "ನೀವು ಮಾಲೀಕತ್ವ ತೆಗೆದುಕೊಂಡ ಒಂದು ನಿರ್ಧಾರವನ್ನು ಹೆಸರಿಸಿ — ನಾಯಕತ್ವ ಆಯ್ಕೆಗಳಲ್ಲಿ ಕಾಣುತ್ತದೆ, ಕೇವಲ ಬಿರುದುಗಳಲ್ಲಿ ಅಲ್ಲ.",
        "lead_tip_collab": "ಇತರರೊಂದಿಗೆ ಹೇಗೆ ಕೆಲಸ ಮಾಡಿದಿರಿ ಉಲ್ಲೇಖಿಸಿ; ಪ್ಯಾನಲ್ ಸಹಕಾರವನ್ನು ಕೇಳುತ್ತದೆ.",
        "lead_tip_impact": "ಇತರರ (ತಂಡ, ಬಳಕೆದಾರರು, ಮೆಂಟೀಗಳು) ಮೇಲಿನ ಪ್ರಭಾವದ ಒಂದು ಸಾಲು ಸೇರಿಸಿ.",
        "conf_low": "ನಿಮ್ಮ ವಿಷಯ ಆರಂಭ — ನಿಧಾನವಾಗಿ, ಒಂದು ಕಾಂಕ್ರೀಟ್ ಕ್ರಿಯೆ ಸೇರಿಸಿ, ಫಲಿತಾಂಶದೊಂದಿಗೆ ಮುಗಿಸಿ. ಕಥೆ ಪೂರ್ಣವಾದಾಗ ಆತ್ಮವಿಶ್ವಾಸ ಬೆಳೆಯುತ್ತದೆ.",
        "conf_result": "ಬಲವಾದ ಆರಂಭ. ಫಲಿತಾಂಶ (ಮೆಟ್ರಿಕ್, ನಿರ್ಧಾರ, ಅಥವಾ ತಂಡ ಪ್ರಭಾವ) ದೊಂದಿಗೆ ಮುಗಿಸಿ.",
        "conf_action": "ಪ್ರಥಮ ಪುರುಷಕ್ಕೆ ಬದಲಾಯಿಸಿ: ನೀವು ತೆಗೆದುಕೊಂಡ 2–3 ನಿರ್ದಿಷ್ಟ ಹಂತಗಳನ್ನು ಹೆಸರಿಸಿ.",
        "conf_high": "ಘನ STAR ರಚನೆ. ಮುಂದಿನ ಬಾರಿ ಆರಂಭಿಕ ಸನ್ನಿವೇಶವನ್ನು ಒಂದು ವಾಕ್ಯಕ್ಕೆ ಬಿಗಿಗೊಳಿಸಿ.",
        "conf_default": "ಒಂದು ಸಾಲಿನಲ್ಲಿ ಸನ್ನಿವೇಶ, ನಂತರ ನೀವು ಮಾಲೀಕತ್ವ ತೆಗೆದುಕೊಂಡದ್ದು, ನಂತರ ಫಲಿತಾಂಶ.",
        "imp_situation": "ಪ್ಯಾನಲ್‌ಗೆ ಸೆಟ್ಟಿಂಗ್ ತಿಳಿಯುವಂತೆ ಸ್ಪಷ್ಟ ಸನ್ನಿವೇಶ ಸೇರಿಸಲಾಗಿದೆ.",
        "imp_task": "ನಿಮ್ಮ ಜವಾಬ್ದಾರಿ / ಗುರಿಯನ್ನು ಹೆಚ್ಚು ಸ್ಪಷ್ಟಪಡಿಸಲಾಗಿದೆ.",
        "imp_action": "ಪ್ರಥಮ-ಪುರುಷ ಕ್ರಿಯೆಗಳಿಗೆ ಒತ್ತು (ನೀವು ಏನು ಮಾಡಿದಿರಿ).",
        "imp_result": "ಫಲಿತಾಂಶವನ್ನು ಕೇಂದ್ರಕ್ಕೆ ತರಲಾಗಿದೆ.",
        "imp_tightened": "ಪದಗಳನ್ನು ಬಿಗಿಗೊಳಿಸಿ ತುಂಬುವಿಕೆ ತೆಗೆದುಹಾಕಲಾಗಿದೆ.",
        "imp_flow": "Situation → Action → Result ಕಡೆಗೆ ಸ್ಪಷ್ಟ ಹರಿವು.",
        "imp_voice": "ನಿಮ್ಮ ವಾಸ್ತವಗಳು ಮತ್ತು ಧ್ವನಿ ಉಳಿಸಲಾಗಿದೆ — ಕಲ್ಪಿತ ಸಾಧನೆಗಳಿಲ್ಲ.",
        "coding_same_bug": "ಸಲ್ಲಿಕೆ ಇನ್ನೂ ಬಗ್ ಆವೃತ್ತಿಯೊಂದಿಗೆ ಹೊಂದಿಕೆಯಾಗುತ್ತದೆ",
        "coding_fixed": "ಮುಖ್ಯ ಬಗ್ ಸರಿಪಡಿಸಿದಂತೆ ಕಾಣುತ್ತದೆ",
        "coding_matches": "ಪರಿಹಾರ ಉದ್ದೇಶಿತ ವರ್ತನೆಯೊಂದಿಗೆ ಹೊಂದಿಕೆಯಾಗುತ್ತದೆ",
        "coding_key_fix": "ನಿಮ್ಮ ಕೋಡ್‌ನಲ್ಲಿ ಮುಖ್ಯ ಫಿಕ್ಸ್ ಮಾದರಿ ಪತ್ತೆಯಾಗಿದೆ",
        "coding_minor": "ಪ್ರೊಡಕ್ಷನ್-ರೆಡಿ ಫಿಕ್ಸ್‌ನಿಂದ ಸಣ್ಣ ರಚನೆ/ಸ್ಪಷ್ಟತೆ ವ್ಯತ್ಯಾಸಗಳು",
        "coding_partial": "ಫಿಕ್ಸ್ ಭಾಗಶಃ — ಕೆಲವು ಬಗ್ ಮಾದರಿಗಳು ಉಳಿಯಬಹುದು",
        "coding_direction": "ನೀವು ಸರಿಯಾದ ದಿಕ್ಕಿನಲ್ಲಿ ಮುಂದುವರಿದಿರಿ",
        "coding_unconfirmed": "ಸಲ್ಲಿಕೆಯಿಂದ ಉದ್ದೇಶಿತ ಫಿಕ್ಸ್ ದೃಢಪಡಿಸಲಾಗಲಿಲ್ಲ",
        "coding_structure": "ಸ್ಪಷ್ಟ ಫಂಕ್ಷನ್ ರಚನೆ",
        "coding_fb_good": "ಟೆಕ್ ಲೀಡ್: “{title}” ನಿಮ್ಮ ಫಿಕ್ಸ್ ವೈಫಲ್ಯ ಮೋಡ್ ಅನ್ನು ಪರಿಹರಿಸುತ್ತದೆ. ಬದಲಾವಣೆ ಅರ್ಥವಾಗುತ್ತದೆ ಮತ್ತು ವಿಮರ್ಶೆಯಲ್ಲಿ ಸ್ವೀಕಾರಾರ್ಹ.",
        "coding_fb_partial": "ಟೆಕ್ ಲೀಡ್: ನೀವು “{title}” ನಲ್ಲಿ ಸಮಸ್ಯೆಯನ್ನು ಗುರುತಿಸಿದ್ದೀರಿ. ಎಡ್ಜ್ ಹ್ಯಾಂಡ್ಲಿಂಗ್ ಮತ್ತು ಓದುವಿಕೆಯನ್ನು ಬಿಗಿಗೊಳಿಸಿ.",
        "coding_fb_bad": "ಟೆಕ್ ಲೀಡ್: “{title}” ಇನ್ನೂ ತಪ್ಪು ಅಥವಾ ಅಪೂರ್ಣವಾಗಿ ಕಾಣುತ್ತದೆ. ವೈಫಲ್ಯ ಮೋಡ್ ಮರುಓದಿ ಮತ್ತು ನಿರೀಕ್ಷಿತ ವರ್ತನೆಯೊಂದಿಗೆ ಹೋಲಿಸಿ.",
    },
}


def _L(language: str | None, key: str, **kwargs):
    """Look up a localized string; fall back to English."""
    lang = (language or "en").lower()
    if lang not in _LOCALE:
        lang = "en"
    d = _LOCALE[lang]
    s = d.get(key)
    if s is None:
        s = _LOCALE["en"].get(key, key)
    if isinstance(s, str) and kwargs:
        try:
            return s.format(**kwargs)
        except Exception:
            return s
    return s



def _parse_json_loose(text: str) -> Any:
    if not text:
        return None
    # strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        # try to find first { ... } or [ ... ]
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    return None


# ---------- Answer-effort detection ----------
# A single shared gate so a low-effort answer ("hi", "idk", one word, etc.)
# is scored low and treated as "no real answer yet" everywhere — STAR scoring,
# the rewriter, and deliberation — instead of drifting to an inflated score
# in some code paths and not others.

def _answer_effort(answer: str) -> dict:
    a = (answer or "").strip()
    words = re.findall(r"[a-zA-Z']+", a)
    wc = len(words)
    return {"word_count": wc, "empty": wc == 0, "trivial": wc <= 6}


# ---------- Resume/JD grounded question generation (works with or without Gemini) ----------

GROUNDED_TEMPLATES = {
    "hr": [
        "I see {skill} on your resume — tell me about a time you had to explain {skill}-related work to someone non-technical.",
        "Projects involving {skill} usually mean coordinating with others. Tell me about a disagreement you had on a {skill} project and how you resolved it.",
        "What drew you to {skill} in the first place, and how does that connect to what excites you about this role?",
        "Tell me about a time your work on {skill} didn't go as planned. How did you communicate that to your team?",
        "Tell me about a time you had to give or receive tough feedback on {skill}-related work. How did that go?",
    ],
    "hr_soft": [
        "You've highlighted {skill} — tell me about a specific moment where that really showed up on the job. What happened?",
        "Everyone claims {skill} on a resume. What's an example that actually proves yours?",
        "Tell me about a time your {skill} was tested under pressure — what made it hard, and what did you do?",
        "How has your approach to {skill} changed since earlier in your career or studies?",
    ],
    "tech_lead": [
        "Walk me through a project where you used {skill}. What was the hardest technical decision you made there?",
        "This role needs {skill}. Tell me about a bug or failure you hit while working with {skill} — how did you find and fix it?",
        "How would you decide whether {skill} is the right choice for a new problem versus an alternative?",
        "Describe the trade-offs you weighed the last time you used {skill} on a real project.",
        "If a junior engineer asked you to explain {skill} in two minutes, what would you say — and where does it usually trip people up?",
    ],
    "tech_lead_resume_only": [
        "I see {skill} on your resume, even though it's not called out in the job description — walk me through a project where you used it. What was the hardest technical decision you made there?",
        "You've listed {skill} — tell me about a bug or failure you hit while working with it. How did you find and fix it?",
        "How would you decide whether {skill} is the right choice for a new problem versus an alternative?",
        "Describe the trade-offs you weighed the last time you used {skill} on a real project.",
    ],
    "hiring_manager": [
        "Tell me about the impact of a project where you used {skill}. How did you or your team measure success?",
        "This role leans on {skill}. Describe a time you owned a {skill}-related deliverable end-to-end — what was the outcome?",
        "How do you prioritize learning {skill} more deeply versus shipping with what you already know?",
        "Tell me about a time your work with {skill} changed how your team or users worked afterward.",
        "If you got this role, what would you want to have shipped using {skill} in your first 90 days?",
    ],
    "hiring_manager_resume_only": [
        "I noticed {skill} on your resume — tell me about the impact of that project. How did you or your team measure success?",
        "Tell me about a time your work with {skill} changed how your team or users worked afterward.",
        "How do you prioritize learning {skill} more deeply versus shipping with what you already know?",
    ],
}

# Classic openers real interviewers actually lead with, before narrowing down
# to resume/JD specifics. Used only for the very first question of a session.
OPENER_QUESTIONS = [
    "Tell me a bit about yourself and what brought you to apply for this role.",
    "Walk me through your resume — what's the throughline you'd want us to notice?",
    "Before we dive in — what made you want to interview for this role specifically?",
]


_SKILL_DISPLAY_OVERRIDES = {
    "aws": "AWS", "gcp": "GCP", "sql": "SQL", "api": "API", "rest": "REST",
    "graphql": "GraphQL", "html": "HTML", "css": "CSS", "nlp": "NLP",
    "ui/ux": "UI/UX", "ci/cd": "CI/CD", "tdd": "TDD", "oop": "OOP",
    "k8s": "Kubernetes", "sre": "SRE", "llm": "LLM", "javascript": "JavaScript",
    "typescript": "TypeScript", "nodejs": "Node.js", "node": "Node.js",
    "fastapi": "FastAPI", "mongodb": "MongoDB", "postgresql": "PostgreSQL",
    "mysql": "MySQL", "pytorch": "PyTorch", "tensorflow": "TensorFlow",
}


def _display_skill(skill: str) -> str:
    return _SKILL_DISPLAY_OVERRIDES.get(skill, skill.title())


# These read oddly in "is X the right tool" / "debugging X" style technical
# templates, so keep them out of the tech_lead/hiring_manager topic pool.
_SOFT_SKILL_WORDS = {
    "leadership", "communication", "teamwork", "problem solving", "ownership",
    "agile", "scrum", "ui/ux",
}


def _resume_jd_topics(resume_text: str, jd_text: str, persona: str = "hr") -> list[tuple[str, bool]]:
    """Returns (display_skill, in_jd) pairs — in_jd is True only when the JD
    actually mentions it, so templates never falsely claim 'this role needs X'
    for something that's only on the resume."""
    resume_skills = extract_skills(resume_text or "")
    jd_skills = extract_skills(jd_text or "")
    if persona in ("tech_lead", "hiring_manager"):
        resume_skills -= _SOFT_SKILL_WORDS
        jd_skills -= _SOFT_SKILL_WORDS
    overlap = sorted(resume_skills & jd_skills)
    jd_only = sorted(jd_skills - resume_skills)
    resume_only = sorted(resume_skills - jd_skills)
    topics = (
        [(_display_skill(s), True) for s in (overlap + jd_only)]
        + [(_display_skill(s), False) for s in resume_only]
    )
    random.shuffle(topics)
    return topics


def _grounded_question(persona: str, resume_text: str, jd_text: str, avoid_questions: list[str] | None = None, language: str = "en") -> str:
    """Build a question that's actually anchored to this candidate's resume/JD,
    without needing Gemini. Falls back to the generic bank only if no
    resume/JD skill signal is found."""
    avoid_questions = avoid_questions or []
    lang = (language or "en").lower()
    # For non-English offline mode, prefer localized fallback bank (English templates
    # would mix languages). Gemini path already handles full localization.
    if lang in ("hi", "kn"):
        pool = [q for q in _fallbacks_for(persona, lang) if not any(_is_too_similar(q, old) for old in avoid_questions)]
        if pool:
            return random.choice(pool)
        return random.choice(_fallbacks_for(persona, lang))
    topics = _resume_jd_topics(resume_text, jd_text, persona=persona)
    # Prefer JD-required skills first so offline questions match the role
    jd_first = sorted(topics, key=lambda x: (0 if x[1] else 1))
    jd_skills = [s for s, in_jd in jd_first if in_jd]
    for skill, in_jd in jd_first[:10]:
        # Skip resume-only stack when the JD already lists role skills
        if not in_jd and jd_skills:
            continue
        is_soft = skill.lower() in _SOFT_SKILL_WORDS
        if persona == "hr":
            template_key = "hr_soft" if is_soft else "hr"
        elif persona in ("tech_lead", "hiring_manager") and not in_jd:
            # Only if JD has NO extractable skills at all
            template_key = f"{persona}_resume_only"
        else:
            template_key = persona
        templates = GROUNDED_TEMPLATES.get(template_key, [])
        for tmpl in random.sample(templates, len(templates)) if templates else []:
            q = tmpl.format(skill=skill)
            if not any(_is_too_similar(q, old) for old in avoid_questions):
                return q
    pool = [q for q in _fallbacks_for(persona, language) if not any(_is_too_similar(q, old) for old in avoid_questions)]
    if pool:
        return random.choice(pool)
    return random.choice(_fallbacks_for(persona, language))


# ---------- Question generation ----------


OPENER_QUESTIONS_HI = [
    "अपने बारे में थोड़ा बताएँ और इस भूमिका के लिए आवेदन करने के पीछे क्या प्रेरणा थी?",
    "अपना रिज्यूमे समझाएँ — हमें कौन सी मुख्य बात नज़र आनी चाहिए?",
    "गहराई में जाने से पहले — इस भूमिका के लिए इंटरव्यू देना आप विशेष रूप से क्यों चाहते थे?",
    "हमें अपनी यात्रा के बारे में बताएँ — आप यहाँ तक कैसे पहुँचे?",
]

OPENER_QUESTIONS_KN = [
    "ನಿಮ್ಮ ಬಗ್ಗೆ ಸ್ವಲ್ಪ ಹೇಳಿ ಮತ್ತು ಈ ಪಾತ್ರಕ್ಕೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಲು ನಿಮ್ಮನ್ನು ತಂದದ್ದು ಏನು?",
    "ನಿಮ್ಮ ರೆಸ್ಯೂಮ್ ಅನ್ನು ವಿವರಿಸಿ — ನಾವು ಗಮನಿಸಬೇಕಾದ ಮುಖ್ಯ ಆಲೋಚನೆ ಏನು?",
    "ಆಳಕ್ಕೆ ಹೋಗುವ ಮೊದಲು — ಈ ಪಾತ್ರಕ್ಕೆ ನಿರ್ದಿಷ್ಟವಾಗಿ ಸಂದರ್ಶನಕ್ಕೆ ಬರಲು ನೀವು ಏಕೆ ಬಯಸಿದಿರಿ?",
    "ನಿಮ್ಮ ಪ್ರಯಾಣದ ಬಗ್ಗೆ ಹೇಳಿ — ನೀವು ಇಲ್ಲಿಗೆ ಹೇಗೆ ಬಂದಿರಿ?",
]

def _openers_for(language: str = "en"):
    lang = (language or "en").lower()
    if lang == "hi":
        return OPENER_QUESTIONS_HI
    if lang == "kn":
        return OPENER_QUESTIONS_KN
    return OPENER_QUESTIONS


FALLBACK_QUESTIONS = {
    "hr": [
        "Tell me about a time you had to work with someone whose working style was very different from yours. How did you handle it?",
        "What motivates you most about this role and our team culture?",
        "Describe a situation where you received critical feedback. What did you do next?",
        "How do you prioritize when everything feels urgent?",
        "Walk me through how you build trust with new teammates.",
        "Tell me about a time you had to deliver difficult news to a teammate or stakeholder.",
        "How do you handle disagreement in a team discussion without damaging relationships?",
        "What kind of environment helps you do your best work?",
        "Describe a time you adapted your communication style for a different audience.",
        "How do you recover when you realize you made a mistake that affected others?",
        "What are you looking for in your next role that you're not getting right now?",
        "Tell me about a time you had to work under a tight deadline with limited information. How did you handle the pressure?",
        "Where do you see yourself in the next few years, and how does this role fit into that?",
        "What's something you'd consider a weakness, and what have you done about it?",
        "Tell me about a time you disagreed with a manager's decision. What did you do?",
        "Why are you looking to leave your current role or program?",
        "What's a piece of feedback that changed how you work?",
        "Tell me about a time you had to say no to someone at work. How did you frame it?",
    ],
    "tech_lead": [
        "Walk me through a technical decision you made recently. What alternatives did you consider?",
        "Describe a production issue you diagnosed. How did you isolate the root cause?",
        "How do you approach testing and reliability for a feature that must not go down?",
        "Explain a system you designed or significantly improved. What were the trade-offs?",
        "Tell me about a time a design failed or had to be reworked. What did you learn?",
        "How do you decide when to refactor versus shipping as-is?",
        "Walk me through how you would debug a performance issue you cannot reproduce locally.",
        "What does good code review look like to you?",
        "Describe a time you had to learn a new technology quickly to deliver something important.",
        "How do you balance technical debt against feature pressure?",
        "How would you explain the difference between a process and a thread to someone new to the concept?",
        "What's the difference between REST and GraphQL, and when would you pick one over the other?",
        "Walk me through how you'd design a rate limiter for an API.",
        "What happens when you type a URL into a browser and hit enter? Go as deep as you're comfortable with.",
        "How do you approach code you didn't write and don't understand yet — say, on your first week on a new team?",
        "Tell me about a time you had to say a deadline wasn't realistic. How did that conversation go?",
    ],
    "hiring_manager": [
        "Tell me about a project you owned end-to-end. What was the business impact?",
        "How do you decide what to work on when the roadmap is ambiguous?",
        "Describe a time you influenced a decision without formal authority.",
        "What does good ownership look like to you in the first 90 days of this role?",
        "Share an example where you measured success beyond 'code shipped'.",
        "Tell me about a time you had to push back on a request from leadership. How did it go?",
        "How do you keep stakeholders aligned when priorities shift mid-project?",
        "Describe a goal you set for yourself that others thought was ambitious. What happened?",
        "How do you decide what not to work on?",
        "Walk me through a time you turned vague requirements into a concrete plan.",
        "Why should we hire you over another candidate with similar experience?",
        "Tell me about the biggest professional challenge you've faced, and how you got through it.",
        "What does success look like for you six months into this role?",
        "Tell me about a time you took initiative on something nobody asked you to do.",
        "How do you handle it when you're given a task with a deadline you know is too tight?",
    ],
}


FALLBACK_QUESTIONS_HI = {
    "hr": [
        "हमें एक समय के बारे में बताएँ जब आपको टीम में किसी मतभेद को सुलझाना पड़ा।",
        "आप दबाव में कैसे संवाद करते हैं? एक उदाहरण दें।",
        "किसी ऐसी भूमिका या प्रोजेक्ट के बारे में बताएँ जहाँ संस्कृति या सहयोग मायने रखता था।",
        "आप प्रतिक्रिया (feedback) कैसे लेते हैं? हाल का एक उदाहरण साझा करें।",
    ],
    "tech_lead": [
        "अपने रिज्यूमे पर एक तकनीकी प्रोजेक्ट चुनें और उसमें सबसे कठिन तकनीकी निर्णय समझाएँ।",
        "एक बग या प्रोडक्शन समस्या के बारे में बताएँ जिसे आपने शुरू से अंत तक ठीक किया।",
        "आपने हाल ही में किस ट्रेड-ऑफ का सामना किया — प्रदर्शन, जटिलता, या डिलीवरी?",
        "रिज्यूमे पर दिख रहे API/बैकएंड अनुभव पर चलें — सबसे कठिन हिस्सा क्या था?",
    ],
    "hiring_manager": [
        "एक प्रोजेक्ट बताएँ जहाँ आपके काम का मापने योग्य प्रभाव पड़ा।",
        "जब प्राथमिकताएँ बदल गईं, आपने कैसे प्राथमिकता तय की?",
        "किसी ऐसी चीज़ का स्वामित्व लेने का उदाहरण दें जो आपके आधिकारिक दायरे से बाहर थी।",
        "इस भूमिका में पहले 90 दिनों में सफलता आपके लिए कैसी दिखेगी?",
    ],
}

FALLBACK_QUESTIONS_KN = {
    "hr": [
        "ತಂಡದಲ್ಲಿ ಭಿನ್ನಾಭಿಪ್ರಾಯವನ್ನು ನೀವು ಪರಿಹರಿಸಿದ ಸಮಯದ ಬಗ್ಗೆ ಹೇಳಿ.",
        "ಒತ್ತಡದಲ್ಲಿ ನೀವು ಹೇಗೆ ಸಂವಹನ ಮಾಡುತ್ತೀರಿ? ಒಂದು ಉದಾಹರಣೆ ನೀಡಿ.",
        "ಸಂಸ್ಕೃತಿ ಅಥವಾ ಸಹಕಾರ ಮುಖ್ಯವಾಗಿದ್ದ ಪಾತ್ರ ಅಥವಾ ಪ್ರಾಜೆಕ್ಟ್ ಬಗ್ಗೆ ಹೇಳಿ.",
        "ನೀವು ಪ್ರತಿಕ್ರಿಯೆಯನ್ನು ಹೇಗೆ ಸ್ವೀಕರಿಸುತ್ತೀರಿ? ಇತ್ತೀಚಿನ ಉದಾಹರಣೆ ಹಂಚಿಕೊಳ್ಳಿ.",
    ],
    "tech_lead": [
        "ನಿಮ್ಮ ರೆಸ್ಯೂಮ್‌ನಿಂದ ಒಂದು ತಾಂತ್ರಿಕ ಪ್ರಾಜೆಕ್ಟ್ ಆಯ್ಕೆಮಾಡಿ ಮತ್ತು ಅಲ್ಲಿ ಕಠಿಣ ತಾಂತ್ರಿಕ ನಿರ್ಧಾರವನ್ನು ವಿವರಿಸಿ.",
        "ನೀವು ಆರಂಭದಿಂದ ಅಂತ್ಯದವರೆಗೆ ಸರಿಪಡಿಸಿದ ಬಗ್ ಅಥವಾ ಪ್ರೊಡಕ್ಷನ್ ಸಮಸ್ಯೆ ಬಗ್ಗೆ ಹೇಳಿ.",
        "ಇತ್ತೀಚೆಗೆ ನೀವು ಎದುರಿಸಿದ ಟ್ರೇಡ್-ಆಫ್ ಏನು — ಕಾರ್ಯಕ್ಷಮತೆ, ಸಂಕೀರ್ಣತೆ, ಅಥವಾ ಡೆಲಿವರಿ?",
        "ರೆಸ್ಯೂಮ್‌ನಲ್ಲಿ ಕಾಣುವ API/ಬ್ಯಾಕೆಂಡ್ ಅನುಭವ — ಕಠಿಣ ಭಾಗ ಯಾವುದು?",
    ],
    "hiring_manager": [
        "ನಿಮ್ಮ ಕೆಲಸದ ಅಳೆಯಬಹುದಾದ ಪ್ರಭಾವವಿದ್ದ ಪ್ರಾಜೆಕ್ಟ್ ಹೇಳಿ.",
        "ಆದ್ಯತೆಗಳು ಬದಲಾದಾಗ ನೀವು ಹೇಗೆ ಆದ್ಯತೆ ನಿರ್ಧರಿಸಿದಿರಿ?",
        "ನಿಮ್ಮ ಅಧಿಕೃತ ವ್ಯಾಪ್ತಿಯ ಹೊರಗಿನದನ್ನು ಮಾಲೀಕತ್ವ ತೆಗೆದುಕೊಂಡ ಉದಾಹರಣೆ ನೀಡಿ.",
        "ಈ ಪಾತ್ರದಲ್ಲಿ ಮೊದಲ 90 ದಿನಗಳಲ್ಲಿ ಯಶಸ್ಸು ನಿಮಗೆ ಹೇಗೆ ಕಾಣುತ್ತದೆ?",
    ],
}

def _fallbacks_for(persona: str, language: str = "en") -> list:
    lang = (language or "en").lower()
    if lang == "hi":
        return FALLBACK_QUESTIONS_HI.get(persona, FALLBACK_QUESTIONS_HI["hr"])
    if lang == "kn":
        return FALLBACK_QUESTIONS_KN.get(persona, FALLBACK_QUESTIONS_KN["hr"])
    return FALLBACK_QUESTIONS.get(persona, FALLBACK_QUESTIONS["hr"])



def _previous_questions(history: list[dict]) -> list[str]:
    """Extract all questions already asked by the panel."""
    qs = []
    for m in history:
        role = (m.get("role") or m.get("persona") or "").lower()
        if role in PERSONAS or role in ("hr", "tech_lead", "hiring_manager"):
            content = (m.get("content") or "").strip()
            if content and len(content) > 10:
                qs.append(content)
    return qs


def _is_too_similar(a: str, b: str) -> bool:
    """Simple similarity check to avoid near-duplicate questions."""
    a_l = set(re.findall(r"[a-z]{4,}", a.lower()))
    b_l = set(re.findall(r"[a-z]{4,}", b.lower()))
    if not a_l or not b_l:
        return False
    overlap = len(a_l & b_l) / max(len(a_l | b_l), 1)
    return overlap > 0.55


def generate_opening_question(
    persona: str,
    resume_text: str,
    jd_text: str,
    analysis: dict | None = None,
    role: str = "sde",
    language: str = "en",
) -> str:
    gaps = []
    if analysis:
        gaps = (analysis.get("missing_skills") or [])[:6]
    gap_line = ", ".join(gaps) if gaps else "none flagged"
    opener_hint = (
        " This is the very first question of the interview — a real interviewer usually opens with "
        "something like 'tell me about yourself' or 'walk me through your resume' before narrowing in. "
        "Feel free to ask that kind of opener, OR go straight to something resume-specific — your call."
        if persona == "hr" else ""
    )
    system = (
        f"You are ONLY the {PERSONAS[persona]['title']} on a hiring panel interviewing for this TARGET ROLE: {role}. "
        f"Your exclusive focus: {PERSONAS[persona]['focus']}. "
        "CRITICAL PRIORITY ORDER for what to ask about:\n"
        "1) The JOB DESCRIPTION and TARGET ROLE — duties, tools, and skills the role requires.\n"
        "2) Skill GAPS vs the JD (things the role needs that the resume is weak on) — especially for Tech Lead.\n"
        "3) Resume only as supporting evidence that the candidate can do the ROLE — do NOT dig into resume-only "
        "stack items (e.g. Node, Tailwind, random frameworks) unless the JD clearly needs them.\n"
        "A real interviewer for a Data Analyst role asks about SQL, data, dashboards, stakeholder communication — "
        "NOT frontend frameworks just because they appear on the resume.\n"
        "Stay in your lane: HR = soft skills/culture for this role; Tech Lead = technical depth for THIS role's stack; "
        "Hiring Manager = impact/ownership in this domain. "
        f"{opener_hint} "
        "Do not greet. Do not explain. Output only the question."
    )
    prompt = (
        f"TARGET ROLE: {role}\n\n"
        f"JOB DESCRIPTION (primary source of truth):\n{jd_text[:2500]}\n\n"
        f"RESUME (supporting context only):\n{resume_text[:1800]}\n\n"
        f"Gaps vs JD to optionally probe: {gap_line}\n\n"
        f"Ask your first interview question for the {role} role, grounded in the JD."
    )
    q = _call_gemini(prompt, system=system, temperature=0.8, language=language)
    if q and len(q) > 15:
        return q.split("\n")[0].strip().strip('"')
    # Gap-aware fallback
    if gaps and persona == "tech_lead":
        g = gaps[0]
        return f"I noticed the role emphasizes {g}. Tell me about a project where you had to ramp up on something similar quickly — what did you do?"
    if persona == "hr":
        # Real interviews almost always open here before narrowing into specifics.
        return random.choice(_openers_for(language))
    grounded = _grounded_question(persona, resume_text, jd_text, avoid_questions=[], language=language)
    if grounded:
        return grounded
    return random.choice(_fallbacks_for(persona, language))


def generate_followup(
    persona: str,
    history: list[dict],
    resume_text: str,
    jd_text: str,
    language: str = "en",
    role: str = "sde",
) -> str:
    """Generate a follow-up that can call back to earlier answers (interviewer memory). Never repeats prior questions."""
    prev_qs = _previous_questions(history)
    prev_block = "\n".join(f"- {q}" for q in prev_qs[-12:]) if prev_qs else "(none yet)"

    transcript = "\n".join(
        f"{m.get('role', m.get('persona', 'unknown')).upper()}: {m.get('content', '')[:400]}"
        for m in history[-10:]
    )
    system = (
        f"You are ONLY the {PERSONAS[persona]['title']} hiring for TARGET ROLE: {role}. "
        f"Your exclusive focus: {PERSONAS[persona]['focus']}. "
        "PRIORITY: Job description + target role over resume-only tech. "
        "Do NOT chase resume stack that is irrelevant to the JD (e.g. Node/Tailwind for a Data Analyst role). "
        "Ask ONE follow-up strictly in your lane: "
        "HR = culture, communication, collaboration for this role; "
        "Tech Lead = technical depth required by the JD/role; "
        "Hiring Manager = impact, ownership, prioritization in this domain. "
        "Prefer referencing something the candidate already said. "
        "Keep it under 2 sentences. CRITICAL: Do NOT repeat any prior question. "
        "Output only the new question."
    )
    prompt = (
        f"TARGET ROLE: {role}\n\n"
        f"JOB DESCRIPTION (primary):\n{jd_text[:2000]}\n\n"
        f"Conversation so far:\n{transcript}\n\n"
        f"Questions ALREADY asked (do not repeat):\n{prev_block}\n\n"
        f"Resume (supporting only):\n{resume_text[:800]}\n\n"
        f"Ask a NEW follow-up for the {role} role, grounded in the JD and conversation."
    )
    q = _call_gemini(prompt, system=system, temperature=0.8, language=language)
    if q and len(q) > 15:
        candidate = q.split("\n")[0].strip().strip('"')
        if not any(_is_too_similar(candidate, old) for old in prev_qs):
            return candidate

    # Fallback: prefer a resume/JD-grounded question first
    grounded = _grounded_question(persona, resume_text, jd_text, avoid_questions=prev_qs, language=language)
    if grounded and not any(_is_too_similar(grounded, old) for old in prev_qs):
        return grounded

    # Otherwise: persona bank + generic callbacks, skipping used ones
    pool = list(_fallbacks_for(persona, language)) + [
        "You mentioned something earlier about ownership — can you expand on a trade-off you made there?",
        "Going back to your previous answer, what would you do differently if you faced the same situation again?",
        "You talked about impact — how did you measure it, and what was the strongest signal?",
        "I'd like to push on the failure-mode side of what you just described. What broke, or nearly broke?",
        "How did stakeholders react to the outcome you described, and what did you change based on their feedback?",
        "What would success look like for you in the first 90 days of this role?",
        "Tell me about a time you had to say no to a request. How did you handle it?",
        "Walk me through how you would approach an unfamiliar technical problem under time pressure.",
    ]
    unused = [p for p in pool if not any(_is_too_similar(p, old) for old in prev_qs)]
    if unused:
        return random.choice(unused)
    return random.choice(pool)


# ---------- STAR detection ----------

def detect_star(answer: str, language: str = "en") -> dict[str, Any]:
    answer = (answer or "").strip()
    empty = {
        "situation": None, "task": None, "action": None, "result": None,
        "score": 0, "notes": _L(language, "star_empty_notes"),
        "missing": ["situation", "task", "action", "result"],
        "tips": [_L(language, "star_empty_tip")],
    }
    if not answer:
        return empty

    effort = _answer_effort(answer)
    if effort["trivial"]:
        return {
            "situation": None, "task": None, "action": None, "result": None,
            "score": min(15, 3 * effort["word_count"]),
            "notes": _L(language, "star_trivial_notes"),
            "missing": ["situation", "task", "action", "result"],
            "tips": [_L(language, "star_trivial_tip")],
        }

    if _gemini_available():
        system = (
            "You are an interview coach analyzing STAR structure.\n"
            "Return STRICT JSON only with these keys:\n"
            "{\n"
            '  "situation": "verbatim excerpt (<=25 words) copied from the answer, or null",\n'
            '  "task": "verbatim excerpt (<=25 words) copied from the answer, or null",\n'
            '  "action": "verbatim excerpt (<=25 words) copied from the answer, or null",\n'
            '  "result": "verbatim excerpt (<=25 words) copied from the answer, or null",\n'
            '  "score": 0-100,\n'
            '  "notes": "one helpful sentence",\n'
            '  "missing": ["situation"|"task"|"action"|"result"],\n'
            '  "tips": ["1-2 concrete tips to improve this answer"]\n'
            "}\n"
            "Scoring guide: all 4 clear=85-100, 3 clear=65-84, 2=45-64, 1=25-44, none=0-24. "
            "Do not invent content that is not in the answer. Excerpts must be copied "
            "verbatim (exact words, no paraphrasing) so they can be highlighted in the "
            "original answer text."
        )
        raw = _call_gemini(f"Answer:\n{answer}", system=system, temperature=0.15, language=language)
        data = _parse_json_loose(raw)
        if isinstance(data, dict) and "score" in data:
            missing = data.get("missing") or []
            if not isinstance(missing, list):
                missing = []
            tips = data.get("tips") or []
            if not isinstance(tips, list):
                tips = [str(tips)] if tips else []
            return {
                "situation": data.get("situation"),
                "task": data.get("task"),
                "action": data.get("action"),
                "result": data.get("result"),
                "score": int(data.get("score", 0)),
                "notes": data.get("notes") or "",
                "missing": missing,
                "tips": tips[:3],
            }

    # Improved heuristic fallback — split into sentences so we can quote the
    # actual part of the candidate's answer that matches each STAR category,
    # instead of a generic "detected" label.
    sentences = [seg.strip() for seg in re.split(r"(?<=[.!?])\s+|\n+", answer.strip()) if seg.strip()]

    def _find_sentence(pattern: str, used: set[int]) -> tuple[str | None, int | None]:
        for idx, sent in enumerate(sentences):
            if idx in used:
                continue
            if re.search(pattern, sent.lower()):
                return sent, idx
        return None, None

    used_idx: set[int] = set()
    s = t = a = r = None
    score = 10
    missing = []
    tips = []

    # Situation
    s, idx = _find_sentence(
        r"\b(when|while|during|at (the|my|our)|in my (role|internship|previous|last)|"
        r"previously|last year|on a project|at [a-z]+|our team was|the (company|product|system) was)\b",
        used_idx,
    )
    if s:
        used_idx.add(idx)
        score += 22
    else:
        missing.append("situation")
        tips.append(_L(language, "star_tip_situation"))

    # Task
    t, idx = _find_sentence(
        r"\b(i was (asked|responsible|tasked|expected)|my (goal|role|job|responsibility) was|"
        r"needed to|had to|the (goal|objective|requirement) was|assigned to)\b",
        used_idx,
    )
    if t:
        used_idx.add(idx)
        score += 18
    else:
        missing.append("task")
        tips.append(_L(language, "star_tip_task"))

    # Action — look for first-person ownership
    a, idx = _find_sentence(
        r"\b(i (implemented|built|designed|led|created|fixed|migrated|refactored|wrote|developed|"
        r"analyzed|debugged|deployed|coordinated|proposed|negotiated|documented)|"
        r"i (took|started|decided|chose|introduced))\b",
        used_idx,
    )
    if a:
        used_idx.add(idx)
        score += 28
    else:
        missing.append("action")
        tips.append(_L(language, "star_tip_action"))

    # Result / impact
    r, idx = _find_sentence(
        r"\b(\d+\s*%|reduced|increased|improved|resulted in|outcome|impact|saved|"
        r"latency|revenue|users?|customers?|shipped|launched|adopted|success|"
        r"before .{0,20} after|from .{0,15} to)\b",
        used_idx,
    )
    if r:
        used_idx.add(idx)
        score += 22
    else:
        missing.append("result")
        tips.append(_L(language, "star_tip_result"))

    score = min(score, 100)
    if score >= 80:
        notes = _L(language, "star_notes_strong")
    elif score >= 55:
        notes = _L(language, "star_notes_partial")
    else:
        notes = _L(language, "star_notes_weak")

    if not tips:
        tips = [_L(language, "star_tip_practice")]

    return {
        "situation": s,
        "task": t,
        "action": a,
        "result": r,
        "score": score,
        "notes": notes,
        "missing": missing,
        "tips": tips[:3],
    }


# ---------- Better-You rewriter ----------

EXAMPLE_OPENERS = {
    "hr": [
        "While working on a group project, a teammate and I disagreed on how to split the work.",
        "During an internship, I got feedback that my updates to the team were too technical.",
        "On a past project, I noticed communication was breaking down between two sub-teams.",
    ],
    "tech_lead": [
        "While building a feature for a project, I ran into a bug that only showed up under load.",
        "I once inherited a script that worked but was fragile, and it broke right before a deadline.",
        "On a personal or academic project, I had to choose between two different technical approaches.",
    ],
    "hiring_manager": [
        "I once owned a small feature end-to-end, from the idea to getting it in front of real users.",
        "On a team project, priorities shifted midway and I had to decide what to drop.",
        "I noticed a recurring problem no one had assigned to anyone, so I took it on myself.",
    ],
}

EXAMPLE_CLOSERS = {
    "hr": " I raised it directly but calmly, we agreed on a way to split ownership, and the project shipped without further friction — I learned to address friction early instead of letting it build.",
    "tech_lead": " I isolated the cause with targeted logging, fixed the underlying issue instead of patching the symptom, and added a test so it wouldn't regress — that cut similar bugs going forward.",
    "hiring_manager": " I tracked a simple before/after metric, shared it with the team, and used it to justify prioritizing the follow-up work — it showed measurable impact, not just 'it's done'.",
}


def _example_answer(question: str, persona: str = "hr", resume_text: str = "", jd_text: str = "") -> str:
    """A model answer showing the *shape* a strong response should take for this
    question — never presented as the candidate's own experience."""
    question = (question or "").strip()
    persona = persona if persona in PERSONAS else "hr"

    if _gemini_available():
        system = (
            f"You are the {PERSONAS[persona]['title']} on a hiring panel. "
            "The candidate gave a near-empty answer to your question. "
            "Write a short MODEL answer (70-110 words) showing the shape of a strong response: "
            "a specific situation, the task/goal, 2-3 concrete first-person actions, and a measurable result. "
            "Use a plausible, generic example — do NOT claim it is the candidate's real experience. "
            "Output only the example answer, no preamble."
        )
        prompt = f"Question: {question}\nResume skills context: {resume_text[:500]}\n"
        out = _call_gemini(prompt, system=system, temperature=0.6)
        if out and len(out) > 30:
            return out.strip()

    topics = _resume_jd_topics(resume_text, jd_text, persona=persona)
    topic = topics[0] if topics else "a recent project"
    opener = random.choice(EXAMPLE_OPENERS.get(persona, EXAMPLE_OPENERS["hr"]))
    closer = EXAMPLE_CLOSERS.get(persona, EXAMPLE_CLOSERS["hr"])
    middle = f" It touched on {topic}, so I first figured out exactly what was going wrong before jumping to a fix."
    return (opener + middle + closer).strip()


def rewrite_answer(
    answer: str,
    persona_feedback: str = "",
    star: dict | None = None,
    question: str = "",
    persona: str = "hr",
    resume_text: str = "",
    jd_text: str = "",
    language: str = "en",
) -> dict:
    """Returns {"mode": "example"|"rewrite", "text": ...}.
    "example" = the answer was too thin to improve, so this shows what a
    strong answer to THIS question looks like, instead of pretending to
    polish a non-answer. "rewrite" = a real improved version of what they said.
    """
    answer = (answer or "").strip()
    effort = _answer_effort(answer)
    if effort["trivial"]:
        return {"mode": "example", "text": _example_answer(question, persona, resume_text, jd_text)}
    if not answer:
        return {"mode": "example", "text": _example_answer(question, persona, resume_text, jd_text)}

    star = star or {}
    missing = star.get("missing") or []
    tips = star.get("tips") or []

    if _gemini_available():
        system = (
            "You are an expert interview coach. Rewrite the candidate's answer so it is clearer, "
            "more structured, and more impactful — while strictly preserving THEIR voice, facts, and meaning.\n"
            "Rules:\n"
            "1. Use a natural STAR flow (Situation → Task → Action → Result) without labeling the parts.\n"
            "2. Prefer concrete first-person verbs and measurable outcomes when present in the original.\n"
            "3. Remove filler, rambling, and vague phrases.\n"
            "4. Do NOT invent achievements, numbers, tools, companies, or outcomes that were not in the original.\n"
            "5. If a STAR part is missing, gently restructure what exists — do not fabricate the missing part.\n"
            "6. Keep length similar or slightly tighter.\n"
            "7. Output ONLY the rewritten answer — no preamble, no quotes, no explanation."
        )
        prompt = f"Original answer:\n{answer}\n"
        if missing:
            prompt += f"\nSTAR parts that are weak/missing: {', '.join(missing)}\n"
        if tips:
            prompt += f"Coach tips: {'; '.join(tips)}\n"
        if persona_feedback:
            prompt += f"\nPanel note the candidate could address:\n{persona_feedback}\n"
        out = _call_gemini(prompt, system=system, temperature=0.4, language=language)
        if out and len(out) > 20:
            out = re.sub(r'^["“]|["”]$', "", out.strip())
            out = re.sub(r"^(here'?s a (better|stronger|improved) (version|answer)[:\s]*)", "", out, flags=re.I)
            return {"mode": "rewrite", "text": out.strip()}

    # Offline fallback — light structural polish, no invented facts
    cleaned = re.sub(r"\s+", " ", answer).strip()
    if not cleaned:
        return {"mode": "example", "text": _example_answer(question, persona, resume_text, jd_text)}
    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."

    words = cleaned.split()
    if len(words) >= 45 and not missing:
        return {"mode": "rewrite", "text": cleaned}

    # Gentle scaffolding only when parts are clearly missing. Picked (not
    # always the first option) so two different thin answers don't come back
    # with the identical bolted-on sentence — this is a last-resort offline
    # patch, not a substitute for the real Gemini rewrite above.
    situation_prefixes = [
        "In that situation, ",
        "Here's the context: ",
        "Setting the scene — ",
    ]
    prefix = ""
    suffix = ""
    if "situation" in missing and not re.match(r"^(when|while|during|in my|at my)", cleaned, re.I):
        prefix = random.choice(situation_prefixes)
    if "result" in missing:
        suffix = " [Add the result here: what changed, what was measured, or how the team/user reacted.]"

    body = cleaned[0].lower() + cleaned[1:] if cleaned and prefix else cleaned
    return {"mode": "rewrite", "text": f"{prefix}{body}{suffix}".strip()}


# ---------- Personalized learning resources ----------

# Curated free / high-signal resources keyed by skill or theme
RESOURCE_CATALOG = {

    "numpy": [
        {"title": "NumPy user guide", "url": "https://numpy.org/doc/stable/user/index.html", "type": "docs"},
        {"title": "NumPy exercises (practice)", "url": "https://github.com/rougier/numpy-100", "type": "practice"},
    ],
    "pandas": [
        {"title": "Pandas documentation", "url": "https://pandas.pydata.org/docs/", "type": "docs"},
        {"title": "Pandas tutorials", "url": "https://pandas.pydata.org/docs/getting_started/intro_tutorials/index.html", "type": "course"},
    ],
    "data analysis": [
        {"title": "Google Data Analytics foundations", "url": "https://www.coursera.org/professional-certificates/google-data-analytics", "type": "course"},
        {"title": "Kaggle Learn – Data Analysis", "url": "https://www.kaggle.com/learn", "type": "course"},
    ],
    "excel": [
        {"title": "Excel practice – Microsoft Learn", "url": "https://learn.microsoft.com/en-us/training/excel/", "type": "course"},
    ],
    "power bi": [
        {"title": "Power BI guided learning", "url": "https://learn.microsoft.com/en-us/power-bi/guided-learning/", "type": "course"},
    ],
    "tableau": [
        {"title": "Tableau free training", "url": "https://www.tableau.com/learn/training", "type": "course"},
    ],
    "statistics": [
        {"title": "Khan Academy Statistics", "url": "https://www.khanacademy.org/math/statistics-probability", "type": "course"},
    ],
    "data visualization": [
        {"title": "From data to viz", "url": "https://www.data-to-viz.com/", "type": "guide"},
    ],
    "python": [
        {"title": "Python Official Tutorial", "url": "https://docs.python.org/3/tutorial/", "type": "docs"},
        {"title": "Real Python – Interviews & Best Practices", "url": "https://realpython.com/", "type": "articles"},
    ],
    "javascript": [
        {"title": "MDN JavaScript Guide", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "type": "docs"},
        {"title": "javascript.info", "url": "https://javascript.info/", "type": "course"},
    ],
    "typescript": [
        {"title": "TypeScript Handbook", "url": "https://www.typescriptlang.org/docs/handbook/intro.html", "type": "docs"},
    ],
    "react": [
        {"title": "React Official Docs (Learn React)", "url": "https://react.dev/learn", "type": "docs"},
    ],
    "fastapi": [
        {"title": "FastAPI Official Tutorial", "url": "https://fastapi.tiangolo.com/tutorial/", "type": "docs"},
    ],
    "django": [
        {"title": "Django Official Tutorial", "url": "https://docs.djangoproject.com/en/stable/intro/tutorial01/", "type": "docs"},
    ],
    "sql": [
        {"title": "SQLBolt – Interactive SQL", "url": "https://sqlbolt.com/", "type": "practice"},
        {"title": "Mode SQL Tutorial", "url": "https://mode.com/sql-tutorial/", "type": "course"},
    ],
    "docker": [
        {"title": "Docker Get Started", "url": "https://docs.docker.com/get-started/", "type": "docs"},
    ],
    "kubernetes": [
        {"title": "Kubernetes Basics Tutorial", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "type": "docs"},
    ],
    "aws": [
        {"title": "AWS Free Tier & Skill Builder", "url": "https://skillbuilder.aws/", "type": "course"},
    ],
    "system design": [
        {"title": "System Design Primer (GitHub)", "url": "https://github.com/donnemartin/system-design-primer", "type": "guide"},
        {"title": "ByteByteGo System Design", "url": "https://bytebytego.com/", "type": "articles"},
    ],
    "algorithms": [
        {"title": "NeetCode roadmap", "url": "https://neetcode.io/", "type": "practice"},
        {"title": "LeetCode Explore", "url": "https://leetcode.com/explore/", "type": "practice"},
    ],
    "data structures": [
        {"title": "VisuAlgo – Data Structures", "url": "https://visualgo.net/en", "type": "practice"},
    ],
    "machine learning": [
        {"title": "Google ML Crash Course", "url": "https://developers.google.com/machine-learning/crash-course", "type": "course"},
    ],
    "leadership": [
        {"title": "Harvard Business Review – Leadership", "url": "https://hbr.org/topic/leadership", "type": "articles"},
    ],
    "communication": [
        {"title": "STAR method practice guide", "url": "https://www.themuse.com/advice/star-interview-method", "type": "guide"},
    ],
    "ownership": [
        {"title": "Ownership in engineering teams (article)", "url": "https://www.managertools.com/", "type": "articles"},
    ],
    "interview": [
        {"title": "STAR Interview Method (Muse)", "url": "https://www.themuse.com/advice/star-interview-method", "type": "guide"},
        {"title": "Pramp – free mock interviews", "url": "https://www.pramp.com/", "type": "practice"},
    ],
    "star": [
        {"title": "How to use the STAR method", "url": "https://www.themuse.com/advice/star-interview-method", "type": "guide"},
        {"title": "Behavioral interview practice", "url": "https://www.pramp.com/", "type": "practice"},
    ],
}


def recommend_resources(
    analysis: dict | None = None,
    star_history: list[dict] | None = None,
    deliberation: dict | None = None,
    language: str = "en",
) -> list[dict[str, Any]]:
    """
    Personalized learning resources based on:
    - missing skills from resume–JD analysis
    - weak STAR areas across answers
    - panel concerns from deliberation
    """
    analysis = analysis or {}
    star_history = star_history or []
    deliberation = deliberation or {}

    needed: list[str] = []

    # From resume gaps — highest priority for personalized resources
    for skill in (analysis.get("missing_skills") or [])[:10]:
        needed.append(skill.lower().strip())
    # Also map common soft gaps mentioned in areas_to_improve
    for area in (analysis.get("areas_to_improve") or []):
        al = str(area).lower()
        for key in ("communication", "ownership", "leadership", "numpy", "pandas", "sql", "python"):
            if key in al:
                needed.append(key)

    # From weak STAR patterns
    weak_star_count = 0
    missing_parts: Counter = Counter()
    for st in star_history:
        if not st:
            continue
        if (st.get("score") or 0) < 60:
            weak_star_count += 1
        for m in st.get("missing") or []:
            missing_parts[m] += 1
    if weak_star_count >= 1 or missing_parts:
        needed.append("star")
        needed.append("interview")
        needed.append("communication")

    # From panel concerns
    individual = deliberation.get("individual") or {}
    concern_text = " ".join(
        " ".join(c for c in (data.get("concerns") or []) if isinstance(c, str))
        for data in individual.values()
        if isinstance(data, dict)
    ).lower()
    for key in ("system design", "algorithms", "leadership", "ownership", "communication", "docker", "kubernetes"):
        if key in concern_text:
            needed.append(key)

    # Deduplicate while preserving order
    seen = set()
    ordered = []
    for k in needed:
        k = k.lower().strip()
        if k and k not in seen:
            seen.add(k)
            ordered.append(k)

    recommendations = []
    for key in ordered:
        # exact or partial match against catalog
        aliases = {
            "numpy": ["numpy", "np"],
            "pandas": ["pandas", "pd"],
            "communication": ["communication", "soft skills", "presentation"],
            "ownership": ["ownership", "accountability"],
            "data analysis": ["data analysis", "data analyst", "analytics"],
            "data visualization": ["data visualization", "visualization", "dashboard", "dashboards"],
            "power bi": ["power bi", "powerbi"],
            "machine learning": ["machine learning", "ml", "sklearn"],
            "sql": ["sql", "mysql", "postgres", "postgresql"],
        }
        matched_keys = []
        if key in RESOURCE_CATALOG:
            matched_keys = [key]
        else:
            for ck, al in aliases.items():
                if key in al or any(a in key for a in al) or key in ck or ck in key:
                    if ck in RESOURCE_CATALOG:
                        matched_keys.append(ck)
            if not matched_keys:
                matched_keys = [ck for ck in RESOURCE_CATALOG if ck in key or key in ck]
        for ck in matched_keys[:1]:
            for res in RESOURCE_CATALOG[ck]:
                recommendations.append({
                    "skill": ck,
                    "title": res["title"],
                    "url": res["url"],
                    "type": res["type"],
                    "reason": _resource_reason(ck, analysis, missing_parts, language=language),
                })

    # Always include a general interview practice resource if nothing else
    if not recommendations:
        for res in RESOURCE_CATALOG["interview"]:
            recommendations.append({
                "skill": "interview",
                "title": res["title"],
                "url": res["url"],
                "type": res["type"],
                "reason": _L(language, "resource_general"),
            })

    # Cap to a useful number
    return recommendations[:10]


def _resource_reason(skill: str, analysis: dict, missing_parts: Counter, language: str = "en") -> str:
    if skill in ("star", "interview", "communication"):
        if missing_parts:
            top = missing_parts.most_common(1)[0][0]
            return _L(language, "resource_star", part=top)
        return _L(language, "resource_star_default")
    missing = [s.lower() for s in (analysis.get("missing_skills") or [])]
    if skill in missing or any(skill in m for m in missing):
        return _L(language, "resource_gap", skill=skill)
    return _L(language, "resource_relevant", skill=skill)


# ---------- Deliberation ----------

def run_deliberation(
    history: list[dict],
    resume_text: str,
    jd_text: str,
    analysis: dict | None = None,
    language: str = "en",
    focus: str = "panel",
) -> dict[str, Any]:
    transcript = "\n".join(
        f"[{m.get('persona') or m.get('role')}] {m.get('content', '')[:500]}"
        for m in history
        if m.get("role") != "system"
    )

    if _gemini_available():
        focus = (focus or "panel").lower()
        if focus in ("behavioral", "hr"):
            panel_desc = (
                "You are ONLY the HR Partner evaluating this candidate. "
                "This was an HR-only interview. Do NOT invent Tech Lead or Hiring Manager voices. "
                "Score only on communication, culture fit, collaboration, ownership language, and clarity. "
                "Return individual.hr only (omit tech_lead and hiring_manager). "
                "Transcript speakers must only be \"HR\"."
            )
            indiv_shape = (
                '"individual": { "hr": {"score": 0-100, "strengths": ["..."], "concerns": ["..."], '
                '"verdict": "advance|lean_advance|hold|reject"} },'
            )
            transcript_rule = "Transcript speakers: only HR."
        elif focus in ("technical", "tech", "tech_lead"):
            panel_desc = (
                "You are ONLY the Tech Lead evaluating this candidate. "
                "This was a Tech Lead-only interview. Do NOT invent HR or Hiring Manager voices. "
                "Score only on technical depth, correctness, trade-offs, debugging mindset, and clarity of technical reasoning. "
                "Return individual.tech_lead only (omit hr and hiring_manager). "
                "Transcript speakers must only be \"Tech Lead\"."
            )
            indiv_shape = (
                '"individual": { "tech_lead": {"score": 0-100, "strengths": ["..."], "concerns": ["..."], '
                '"verdict": "advance|lean_advance|hold|reject"} },'
            )
            transcript_rule = "Transcript speakers: only Tech Lead."
        elif focus in ("hiring_manager", "hm"):
            panel_desc = (
                "You are ONLY the Hiring Manager evaluating this candidate. "
                "This was a Hiring Manager-only interview. Do NOT invent HR or Tech Lead voices. "
                "Score only on impact, ownership, prioritization, team fit, and business judgment. "
                "Return individual.hiring_manager only (omit hr and tech_lead). "
                "Transcript speakers must only be \"Hiring Manager\"."
            )
            indiv_shape = (
                '"individual": { "hiring_manager": {"score": 0-100, "strengths": ["..."], "concerns": ["..."], '
                '"verdict": "advance|lean_advance|hold|reject"} },'
            )
            transcript_rule = "Transcript speakers: only Hiring Manager."
        else:
            panel_desc = (
                "You simulate a hiring panel of three people: HR, Tech Lead, and Hiring Manager. "
                "Produce a realistic deliberation transcript where they discuss the candidate, "
                "including at least one genuine disagreement, then reach a reasoned consensus."
            )
            indiv_shape = (
                '"individual": { '
                '"hr": {"score": 0-100, "strengths": ["..."], "concerns": ["..."], "verdict": "advance|lean_advance|hold|reject"}, '
                '"tech_lead": {...}, "hiring_manager": {...} },'
            )
            transcript_rule = "Transcript speakers: HR, Tech Lead, Hiring Manager."

        system = (
            panel_desc + "\n\n"
            "SCORING PHILOSOPHY — read carefully:\n"
            "Judge the candidate on the substance, relevance, and correctness of what they actually said in "
            "response to each question — not on whether it was formatted as a rigid Situation-Task-Action-Result "
            "story. STAR is a coaching aid shown separately per-answer; it is NOT a panel scoring criterion. "
            "An opener like 'tell me about yourself' or 'walk me through your resume' is NOT a behavioral "
            "question and should never be penalized for lacking Situation/Task/Action/Result — judge it on "
            "clarity, relevance to the role, and genuine signal about the candidate instead. "
            "A technical answer that is correct and clearly explained deserves real credit even if it isn't "
            "phrased as a story. Reserve low scores for answers that are actually thin, evasive, off-topic, "
            "or factually wrong — not for answers that are simply structured differently than STAR.\n\n"
            "Return strict JSON with this shape:\n"
            "{\n"
            '  "transcript": [{"speaker": "...", "text": "..."}, ...],\n'
            f"  {indiv_shape}\n"
            '  "consensus": {"score": 0-100, "verdict": "...", "summary": "...", "key_disagreement": "...", "recommendation": "..."},\n'
            '  "follow_up_questions": ["q1", "q2", "q3"]\n'
            "}\n"
            f"{transcript_rule} "
            "Scores must be grounded ONLY in this interview transcript — never invent a fixed score. "
            "Always return exactly 3 follow_up_questions "
            "the interviewer would still want the candidate to answer in a next round. "
            "Ground every comment in the actual transcript and resume — do NOT use generic feedback "
            "that could apply to any candidate. Quote or paraphrase specific things the candidate said."
        )

        prompt = f"""Interview transcript:\n{transcript[:6000]}\n\nResume excerpt:\n{resume_text[:1500]}\n\nJD excerpt:\n{jd_text[:1200]}\n"""
        raw = _call_gemini(prompt, system=system, temperature=0.65, language=language)
        data = _parse_json_loose(raw)
        if isinstance(data, dict) and "transcript" in data:
            if not data.get("follow_up_questions"):
                data["follow_up_questions"] = list(_L(language, "gemini_followups"))
            cons = data.get("consensus") or {}
            indiv = data.get("individual") or {}
            if focus in ("behavioral", "hr"):
                if "hr" in indiv:
                    indiv = {"hr": indiv["hr"]}
                # keep only HR transcript lines if possible
                tr = data.get("transcript") or []
                tr = [x for x in tr if str(x.get("speaker", "")).lower() in ("hr", "hr partner", "एचआर", "hr पार्टनर")] or tr[:2]
                data["transcript"] = tr
                if indiv.get("hr") and isinstance(indiv["hr"].get("score"), (int, float)):
                    cons["score"] = indiv["hr"]["score"]
                cons["key_disagreement"] = ""
            elif focus in ("technical", "tech", "tech_lead"):
                if "tech_lead" in indiv:
                    indiv = {"tech_lead": indiv["tech_lead"]}
                tr = data.get("transcript") or []
                tr = [x for x in tr if "tech" in str(x.get("speaker", "")).lower() or "टेक" in str(x.get("speaker", ""))] or tr[:2]
                data["transcript"] = tr
                if indiv.get("tech_lead") and isinstance(indiv["tech_lead"].get("score"), (int, float)):
                    cons["score"] = indiv["tech_lead"]["score"]
                cons["key_disagreement"] = ""
            else:
                if not cons.get("key_disagreement"):
                    cons["key_disagreement"] = _L(language, "gemini_disagreement")
            data["individual"] = indiv
            data["consensus"] = cons
            data["focus"] = focus
            return data

    # High-quality offline fallback deliberation (localized)
    return _fallback_deliberation(history, analysis, language=language, focus=focus)


# Transcript language pools, keyed by score tier, so the deliberation reads
# differently between runs AND actually reflects how the interview went —
# instead of one fixed script with only the number changed.
_TIER_LINES = {
    "low": {
        "hr": [
            "Honestly, I didn't get enough from the candidate to assess culture fit. Most answers were one-liners with no real story behind them.",
            "I can't call this a strong communication signal either way — there just wasn't enough substance in the responses to go on.",
        ],
        "tech_lead": [
            "There's no technical depth to evaluate here. The answers didn't get past a sentence, so I have nothing to sanity-check against the role.",
            "I'd normally probe failure modes and trade-offs, but the candidate didn't give us a real example to dig into.",
        ],
        "hiring_manager": [
            "I don't see ownership or impact signal in what was submitted — the answers were too short to show any of that.",
            "From a hiring-manager lens, this session doesn't give me enough to recommend moving forward as-is.",
        ],
    },
    "mid": {
        "hr": [
            f"Communication was okay — when they talked about “{{snippet}}”, the framing was reasonable, though it stayed fairly high-level.",
            "Some good signal on collaboration, but a couple of answers could have gone deeper into how they actually handled friction.",
        ],
        "tech_lead": [
            "Technical depth is there in places but inconsistent — the story around “{snippet}” had potential but skipped past the harder trade-offs.",
            "Decent structure, though I'd want a stronger example of debugging or a failure mode before I'm fully convinced.",
        ],
        "hiring_manager": [
            "Ownership signal is present but not fully proven yet — I'd want to see a clearer measurable outcome next round.",
            "There's a reasonable impact story here, around “{snippet}”, but it's more implied than demonstrated with numbers.",
        ],
    },
    "high": {
        "hr": [
            "Strong communication throughout — the story about “{snippet}” showed real self-awareness and collaboration.",
            "Culture-fit signal is genuinely positive here; the candidate handled the conversation with clarity and confidence.",
        ],
        "tech_lead": [
            "Solid technical depth — “{snippet}” showed real ownership of a hard problem, including the trade-offs involved.",
            "This is one of the stronger technical stories I've heard this round; the reasoning held up under follow-up.",
        ],
        "hiring_manager": [
            "Clear ownership and measurable impact in the “{snippet}” story — exactly the kind of signal this role needs.",
            "Strong impact orientation. I'd be comfortable moving this candidate forward on the strength of this round alone.",
        ],
    },
}

_CONSENSUS_TEXT = {
    "low": {
        "summary": (
            "The panel did not see enough substantive answers this round to fairly evaluate the candidate — "
            "most responses were too short to show real Situation/Task/Action/Result content. "
            "This score reflects the lack of demonstrated content, not a judgment on the candidate's actual ability."
        ),
        "key_disagreement": "There wasn't enough material for the panel to meaningfully disagree — the main gap was thin answers across the board.",
        "recommendation": "Re-run the interview and answer each question with a full example (a few sentences minimum) before the panel can give a real read.",
    },
    "mid": {
        "summary": (
            "The panel saw a mixed round — some reasonable signal on communication and ownership, "
            "with technical depth and result specificity being the main gaps to close."
        ),
        "key_disagreement": "Tech Lead wanted more depth on failure modes; Hiring Manager weighted the ownership signal more generously.",
        "recommendation": "Advance to a focused follow-up round on technical depth and measurable outcomes, while reinforcing the communication strengths shown.",
    },
    "high": {
        "summary": (
            "The panel saw a strong, well-structured round with clear ownership, solid technical reasoning, "
            "and good communication throughout."
        ),
        "key_disagreement": "Minor disagreement on how much further to probe technical edge cases, but all three leaned toward advancing.",
        "recommendation": "Advance to the next round; use a technical deep-dive to confirm depth on edge cases and scale.",
    },
}


def _score_tier(score: float) -> str:
    if score < 35:
        return "low"
    if score < 68:
        return "mid"
    return "high"


def _fallback_deliberation(history: list[dict], analysis: dict | None, language: str = "en", focus: str = "panel") -> dict[str, Any]:
    answers = [m for m in history if m.get("role") == "candidate"]
    n = len(answers)

    # Pair each candidate answer with the panel question that immediately
    # preceded it (candidate messages don't carry their own question field —
    # it's whatever the previous persona message in the ordered history asked).
    def _preceding_question(msg: dict) -> str:
        idx = history.index(msg)
        for prev in reversed(history[:idx]):
            if prev.get("role") in PERSONAS:
                return (prev.get("content") or "")
        return ""

    def _is_opener(q: str) -> bool:
        ql = q.lower()
        return (
            "tell me a bit about yourself" in ql
            or "walk me through your resume" in ql
            or "what made you want to interview" in ql
        )

    # Pull snippets only from substantive (non-trivial) answers, so a "hi" never
    # gets quoted back as if it were a real story.
    snippets = []
    for a in answers:
        c = (a.get("content") or "").strip().replace("\n", " ")
        if c and _answer_effort(c)["word_count"] > 6:
            snippets.append(c[:120] + ("…" if len(c) > 120 else ""))
    snippet_text = random.choice(snippets) if snippets else _L(language, "snippet_default")

    star_scores = []
    for a in answers:
        if _is_opener(_preceding_question(a)):
            continue
        st = a.get("star") or {}
        if isinstance(st, dict) and isinstance(st.get("score"), (int, float)):
            star_scores.append(st["score"])
    star_avg = sum(star_scores) / len(star_scores) if star_scores else 60  # neutral if only openers were answered

    resume_score = analysis.get("overall_score", 50) if analysis else 50

    # STAR structure is a coaching aid, not the main driver of the panel's
    # overall read — a candidate can give substantive, correct, relevant
    # answers without formatting them as a rigid story. Weight it as one
    # input among several instead of 80% of the outcome.
    # Score from THIS interview's answers (STAR + length/effort), not fixed templates
    effort_scores = []
    for a in answers:
        c = (a.get("content") or "").strip()
        eff = _answer_effort(c)
        # Map word count + trivial flag into 0-100 signal
        if eff.get("trivial"):
            effort_scores.append(min(25, 4 * eff.get("word_count", 0)))
        else:
            effort_scores.append(min(100, 20 + eff.get("word_count", 0) * 2.5))
    effort_avg = sum(effort_scores) / len(effort_scores) if effort_scores else 15

    if n == 0:
        base = 0
    elif analysis and analysis.get("overall_score") is not None:
        base = 0.45 * star_avg + 0.25 * effort_avg + 0.25 * resume_score + 0.05 * min(100, n * 12)
    else:
        # Pure interview (no resume): score only from what was said
        base = 0.55 * star_avg + 0.40 * effort_avg + 0.05 * min(100, n * 12)
    base = max(0, min(100, base + random.randint(-5, 5)))

    hr_score = max(0, min(100, round(base + random.randint(-6, 8))))
    tech_score = max(0, min(100, round(base + random.randint(-10, 5))))
    hm_score = max(0, min(100, round(base + random.randint(-4, 10))))
    focus_l = (focus or "panel").lower()

    tier = _score_tier(base)

    # Localized tier lines
    tier_map = {
        "low": {
            "hr": _L(language, "tier_low_hr"),
            "tech_lead": _L(language, "tier_low_tech"),
            "hiring_manager": _L(language, "tier_low_hm"),
        },
        "mid": {
            "hr": _L(language, "tier_mid_hr"),
            "tech_lead": _L(language, "tier_mid_tech"),
            "hiring_manager": _L(language, "tier_mid_hm"),
        },
        "high": {
            "hr": _L(language, "tier_high_hr"),
            "tech_lead": _L(language, "tier_high_tech"),
            "hiring_manager": _L(language, "tier_high_hm"),
        },
    }
    lines = tier_map[tier]

    def pick(speaker_key: str) -> str:
        raw = random.choice(lines[speaker_key])
        try:
            return raw.format(snippet=snippet_text)
        except Exception:
            return raw

    if focus_l in ("behavioral", "hr"):
        composite_score = int(hr_score)
    elif focus_l in ("technical", "tech", "tech_lead"):
        composite_score = int(tech_score)
    elif focus_l in ("hiring_manager", "hm"):
        composite_score = int(hm_score)
    else:
        composite_score = int(round((hr_score + tech_score + hm_score) / 3))
    next_line = _L(language, "next_low") if tier == "low" else _L(language, "next_mid")
    if focus_l in ("behavioral", "hr"):
        transcript = [
            {"speaker": _L(language, "speaker_hr"), "text": pick("hr")},
            {
                "speaker": _L(language, "speaker_hr"),
                "text": _L(language, "composite", score=composite_score) + next_line,
            },
        ]
    elif focus_l in ("technical", "tech", "tech_lead"):
        transcript = [
            {"speaker": _L(language, "speaker_tech"), "text": pick("tech_lead")},
            {
                "speaker": _L(language, "speaker_tech"),
                "text": _L(language, "composite", score=composite_score) + next_line,
            },
        ]
    elif focus_l in ("hiring_manager", "hm"):
        transcript = [
            {"speaker": _L(language, "speaker_hm"), "text": pick("hiring_manager")},
            {
                "speaker": _L(language, "speaker_hm"),
                "text": _L(language, "composite", score=composite_score) + next_line,
            },
        ]
    else:
        transcript = [
            {"speaker": _L(language, "speaker_hr"), "text": pick("hr")},
            {"speaker": _L(language, "speaker_tech"), "text": pick("tech_lead")},
            {"speaker": _L(language, "speaker_hm"), "text": pick("hiring_manager")},
            {
                "speaker": _L(language, "speaker_hm"),
                "text": _L(language, "composite", score=composite_score) + next_line,
            },
        ]

    def pack(score: int, strengths: list, concerns: list, verdict: str):
        return {
            "score": score,
            "strengths": strengths,
            "concerns": concerns,
            "verdict": verdict,
        }

    if tier == "low":
        individual = {
            "hr": pack(hr_score, [], list(_L(language, "hr_concerns_low")), "hold" if hr_score >= 30 else "reject"),
            "tech_lead": pack(tech_score, [], list(_L(language, "tech_concerns_low")), "hold" if tech_score >= 30 else "reject"),
            "hiring_manager": pack(hm_score, [], list(_L(language, "hm_concerns_low")), "hold" if hm_score >= 30 else "reject"),
        }
    elif tier == "mid":
        individual = {
            "hr": pack(hr_score, list(_L(language, "hr_strengths_mid")), list(_L(language, "hr_concerns_mid")), "lean_advance" if hr_score >= 60 else "hold"),
            "tech_lead": pack(tech_score, list(_L(language, "tech_strengths_mid")), list(_L(language, "tech_concerns_mid")), "hold" if tech_score < 65 else "lean_advance"),
            "hiring_manager": pack(hm_score, list(_L(language, "hm_strengths_mid")), list(_L(language, "hm_concerns_mid")), "lean_advance" if hm_score >= 60 else "hold"),
        }
    else:
        individual = {
            "hr": pack(hr_score, list(_L(language, "hr_strengths_high")), [], "advance" if hr_score >= 75 else "lean_advance"),
            "tech_lead": pack(tech_score, list(_L(language, "tech_strengths_high")), list(_L(language, "tech_concerns_high")), "advance" if tech_score >= 75 else "lean_advance"),
            "hiring_manager": pack(hm_score, list(_L(language, "hm_strengths_high")), [], "advance"),
        }

    consensus_score = int(round((hr_score + tech_score + hm_score) / 3))
    if consensus_score >= 75:
        verdict = "advance"
    elif consensus_score >= 60:
        verdict = "lean_advance"
    elif consensus_score >= 45:
        verdict = "hold"
    else:
        verdict = "reject"

    if focus_l in ("behavioral", "hr"):
        individual = {"hr": individual["hr"]}
        consensus_score = int(individual["hr"]["score"])
    elif focus_l in ("technical", "tech", "tech_lead"):
        individual = {"tech_lead": individual["tech_lead"]}
        consensus_score = int(individual["tech_lead"]["score"])
    elif focus_l in ("hiring_manager", "hm"):
        individual = {"hiring_manager": individual["hiring_manager"]}
        consensus_score = int(individual["hiring_manager"]["score"])

    if consensus_score >= 75:
        verdict = "advance"
    elif consensus_score >= 60:
        verdict = "lean_advance"
    elif consensus_score >= 45:
        verdict = "hold"
    else:
        verdict = "reject"

    disagreement = ""
    if focus_l not in ("behavioral", "hr", "technical", "tech", "tech_lead", "hiring_manager", "hm"):
        disagreement = _L(language, f"consensus_{tier}_disagreement")

    return {
        "transcript": transcript,
        "individual": individual,
        "consensus": {
            "score": consensus_score,
            "verdict": verdict,
            "summary": _L(language, f"consensus_{tier}_summary"),
            "key_disagreement": disagreement,
            "recommendation": _L(language, f"consensus_{tier}_recommendation"),
        },
        "follow_up_questions": list(_L(language, "follow_low" if tier == "low" else "follow_mid")),
        "answers_reviewed": n,
        "focus": focus_l,
    }




def detect_leadership_signals(answer: str, language: str = "en") -> dict:
    """Lightweight leadership / ownership signals — aligned with Girl Geeks leadership theme."""
    lower = (answer or "").lower()
    signals = []
    if re.search(r"\b(i led|i owned|i coordinated|i mentored|i facilitated|i organized)\b", lower):
        signals.append("ownership_language")
    if re.search(r"\b(team|teammate|collaborat|paired|stakeholder)\b", lower):
        signals.append("collaboration")
    if re.search(r"\b(decided|prioritized|trade-?off|influenced|proposed)\b", lower):
        signals.append("decision_making")
    if re.search(r"\b(mentored|helped others|onboarded|coached|supported the team)\b", lower):
        signals.append("peer_support")
    if re.search(r"\b(after a break|returning|career break|gap year|came back to)\b", lower):
        signals.append("returner_narrative")
    score = min(100, 20 * len(signals) + (15 if "ownership_language" in signals else 0))
    tips = []
    if "ownership_language" not in signals:
        tips.append(_L(language, "lead_tip_ownership"))
    if "collaboration" not in signals:
        tips.append(_L(language, "lead_tip_collab"))
    if not signals:
        tips.append(_L(language, "lead_tip_impact"))
    return {"signals": signals, "score": score, "tips": tips[:2]}


def mentor_note(analysis: dict | None, deliberation: dict | None, star_avg: float | None = None, language: str = "en") -> str:
    """Warm mentor-style closing note — mentorship pillar of Girl Geeks."""
    analysis = analysis or {}
    deliberation = deliberation or {}
    cons = deliberation.get("consensus") or {}
    verdict = (cons.get("verdict") or "hold").replace("_", " ")
    gaps = (analysis.get("missing_skills") or [])[:3]
    if _gemini_available():
        system = (
            "You are a supportive career mentor for women engineering students. "
            "Write 3-4 sentences: acknowledge effort, name 1 strength, 1 growth area, "
            "and one encouraging next step. No fluff, no condescension."
        )
        prompt = (
            f"Verdict: {verdict}. STAR avg: {star_avg}. "
            f"Skill gaps: {gaps}. Summary: {cons.get('summary', '')[:300]}"
        )
        out = _call_gemini(prompt, system=system, temperature=0.5, language=language)
        if out and len(out) > 40:
            return out.strip()
    strength = _L(language, "strength_default")
    growth = _L(language, "growth_gap", gap=gaps[0]) if gaps else _L(language, "growth_default")
    return _L(language, "mentor", strength=strength, growth=growth)


def returner_friendly_prompt_addon(enabled: bool) -> str:
    if not enabled:
        return ""
    return (
        " The candidate may be returning after a career break or is an early-career woman engineer. "
        "Prefer questions that allow transferrable skills and recent projects; avoid assuming continuous employment."
    )


def confidence_tip(answer: str, star: dict | None, confidence: int | None = None, language: str = "en") -> str:
    """One short coaching tip based on STAR + optional self-rated confidence."""
    star = star or {}
    missing = star.get("missing") or []
    score = star.get("score") or 0
    conf = confidence if confidence is not None else 3

    if _gemini_available():
        system = (
            "Give ONE short interview coaching tip (max 2 sentences). "
            "Be specific and kind. No preamble."
        )
        prompt = (
            f"Answer excerpt: {answer[:500]}\n"
            f"STAR score: {score}. Missing parts: {missing}. "
            f"Candidate confidence self-rating: {conf}/5."
        )
        out = _call_gemini(prompt, system=system, temperature=0.4, language=language)
        if out and len(out) > 15:
            return out.split("\n")[0].strip()

    if conf <= 2 and score < 55:
        return _L(language, "conf_low")
    if "result" in missing:
        return _L(language, "conf_result")
    if "action" in missing:
        return _L(language, "conf_action")
    if score >= 75:
        return _L(language, "conf_high")
    return _L(language, "conf_default")


def improvement_bullets(original: str, rewritten: str, star: dict | None = None, language: str = "en") -> list[str]:
    """What improved in the Better You version."""
    star = star or {}
    bullets = []
    missing = star.get("missing") or []
    if "situation" in missing:
        bullets.append(_L(language, "imp_situation"))
    if "task" in missing:
        bullets.append(_L(language, "imp_task"))
    if "action" in missing:
        bullets.append(_L(language, "imp_action"))
    if "result" in missing:
        bullets.append(_L(language, "imp_result"))
    if not bullets:
        if len(rewritten or "") < len(original or "") * 0.9:
            bullets.append(_L(language, "imp_tightened"))
        bullets.append(_L(language, "imp_flow"))
        bullets.append(_L(language, "imp_voice"))
    return bullets[:4]


def enrich_resume_summary(analysis: dict, resume_text: str, jd_text: str) -> str:
    if not _gemini_available():
        return analysis.get("summary", "")
    system = (
        "You are a career coach. Given a resume–JD match analysis, write a short, encouraging, "
        "specific 3–4 sentence summary for the candidate. No fluff."
    )
    prompt = json.dumps(analysis, indent=2)[:3000]
    out = _call_gemini(prompt, system=system, temperature=0.4)
    return out or analysis.get("summary", "")