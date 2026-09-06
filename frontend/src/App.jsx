import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload, Briefcase, Users, MessageSquare, Sparkles, Target,
  ChevronRight, Trophy, AlertTriangle, CheckCircle2, XCircle,
  Mic, Send, Scale, RefreshCw, FileText, ArrowRight, Play, Download, Clock, Code2, Bug, Globe
} from 'lucide-react'
import { api, getToken } from './api'
import {
  getStoredLanguage,
  setStoredLanguage,
  t as translate,
  speechLang,
  languagePromptName,
  SUPPORTED_LANGUAGES,
} from './i18n'

const API = '/api'

async function authFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers })
}

function useT(lang) {
  return useCallback((key, vars) => translate(key, lang, vars), [lang])
}

function ScoreRing({ score }) {
  const pct = Math.max(0, Math.min(100, score || 0))
  return (
    <div className="score-ring" style={{ '--pct': pct }}>
      <span>{Math.round(pct)}</span>
    </div>
  )
}

function StarBreakdown({ star, t }) {
  if (!star) return null
  const rows = [
    { key: 'situation', letter: 'S', label: t('situation'), color: 'var(--hr)' },
    { key: 'task', letter: 'T', label: t('task'), color: 'var(--tech)' },
    { key: 'action', letter: 'A', label: t('action'), color: 'var(--hm)' },
    { key: 'result', letter: 'R', label: t('result'), color: 'var(--success)' },
  ]
  return (
    <div className="star-breakdown">
      {rows.map(({ key, letter, label, color }) => {
        const text = star[key]
        return (
          <div className={`star-breakdown-row ${text ? '' : 'is-missing'}`} key={key}>
            <span className="star-breakdown-letter" style={{ background: text ? color : 'var(--bg-soft)', color: text ? '#fff' : 'var(--text-dim)' }}>
              {letter}
            </span>
            <div className="star-breakdown-body">
              <div className="star-breakdown-label" style={{ color: text ? color : 'var(--text-dim)' }}>{label}</div>
              <div className="star-breakdown-text">
                {text ? `“${text}”` : t('notClearlyPresent')}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function StarChips({ star, t }) {
  if (!star) return null
  const keys = [
    ['situation', 'S'],
    ['task', 'T'],
    ['action', 'A'],
    ['result', 'R'],
  ]
  return (
    <div>
      <div className="star-row">
        {keys.map(([k, letter]) => (
          <span key={k} className={`star-chip ${star[k] ? 'on' : ''}`} title={star[k] || `${letter} ${t('notDetected')}`}>
            {letter} · {star[k] ? t('detected') : t('weak')}
          </span>
        ))}
        {typeof star.score === 'number' && (
          <span className="star-chip on">STAR {star.score}/100</span>
        )}
      </div>
      {star.notes && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 6 }}>{star.notes}</p>
      )}
      {(star.tips || []).length > 0 && (
        <ul style={{ fontSize: '0.78rem', color: 'var(--warning)', marginTop: 4, paddingLeft: 16 }}>
          {star.tips.map((tipItem, i) => <li key={i}>{tipItem}</li>)}
        </ul>
      )}
    </div>
  )
}

function LanguageSelector({ lang, setLang }) {
  return (
    <div className="lang-selector" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <Globe size={14} style={{ opacity: 0.7 }} />
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value)}
        aria-label="Language"
        style={{
          padding: '6px 10px',
          borderRadius: 8,
          border: '1px solid var(--border)',
          background: 'var(--bg-soft)',
          color: 'var(--text)',
          fontSize: '0.82rem',
          cursor: 'pointer',
          maxWidth: 140,
        }}
      >
        {SUPPORTED_LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.native}
          </option>
        ))}
      </select>
    </div>
  )
}

export default function App({ lang: langProp, setLang: setLangProp, embed = false } = {}) {
  const [langInternal, setLangState] = useState(() => getStoredLanguage())
  const lang = langProp != null ? langProp : langInternal
  const t = useT(lang)

  const setLang = useCallback((code) => {
    if (setLangProp) setLangProp(code)
    else {
      setLangState(code)
      setStoredLanguage(code)
    }
  }, [setLangProp])

  const navigate = useNavigate()

  const personaMeta = {
    hr: { label: t('personaHrShort'), short: 'HR', className: 'hr', color: '#6D4FE0' },
    tech_lead: { label: t('personaTechShort'), short: 'Tech Lead', className: 'tech_lead', color: '#2563EB' },
    hiring_manager: { label: t('personaHmShort'), short: 'Hiring Manager', className: 'hiring_manager', color: '#12805F' },
  }

  const [entryMode, setEntryMode] = useState('home') // home | analysis | quick | coding | debug
  const [panelFocus, setPanelFocus] = useState('panel') // panel | behavioral | technical | hiring_manager
  const [step, setStep] = useState('home')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [candidateName, setCandidateName] = useState('')
  const [jd, setJd] = useState('')
  const [resumeFile, setResumeFile] = useState(null)
  const [resumeText, setResumeText] = useState('')
  const [useText, setUseText] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [history, setHistory] = useState([])
  const [answer, setAnswer] = useState('')
  const [turns, setTurns] = useState(0)
  const [canDeliberate, setCanDeliberate] = useState(false)
  const [deliberation, setDeliberation] = useState(null)
  const [resources, setResources] = useState([])
  const [role, setRole] = useState('data analyst')
  const [customRole, setCustomRole] = useState('')
  const [sampleAnswers, setSampleAnswers] = useState([])
  const [timerSec, setTimerSec] = useState(0)
  const [timerOn, setTimerOn] = useState(false)
  const timerRef = useRef(null)
  const [pressureMode, setPressureMode] = useState(false)
  const [answerTimer, setAnswerTimer] = useState(90)
  const answerTimerRef = useRef(null)
  const [returnerMode, setReturnerMode] = useState(false)
  const [mentorNote, setMentorNote] = useState('')
  const [starAvg, setStarAvg] = useState(null)
  const [expandedStars, setExpandedStars] = useState({})
  const [codingMode, setCodingMode] = useState(null)
  const [codingProblem, setCodingProblem] = useState(null)
  const [codingSubmission, setCodingSubmission] = useState('')
  const [codingReview, setCodingReview] = useState(null)
  const [usedCodingIds, setUsedCodingIds] = useState([])
  const [codingDifficulty, setCodingDifficulty] = useState('easy')
  const [codingPicker, setCodingPicker] = useState(null)
  const [codingLanguage, setCodingLanguage] = useState('python')
  const [listening, setListening] = useState(false)
  const chatEndRef = useRef(null)

  const prevLangRef = useRef(lang)
  // When UI language changes mid-session, re-localize analysis / deliberation / resources
  useEffect(() => {
    const prev = prevLangRef.current
    prevLangRef.current = lang
    if (prev === lang) return
    if (!sessionId) return
    if (!analysis && !deliberation) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await authFetch(`${API}/session/relocalize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, language: lang }),
        })
        if (!res.ok || cancelled) return
        const data = await res.json()
        if (cancelled) return
        if (data.analysis) setAnalysis(data.analysis)
        if (Array.isArray(data.resources)) setResources(data.resources)
        if (data.deliberation) setDeliberation(data.deliberation)
        if (data.mentor_note != null) setMentorNote(data.mentor_note || '')
        if (data.star_avg != null) setStarAvg(data.star_avg)
      } catch (_) {
        /* keep existing content */
      }
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  // Continue incomplete interview from History
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('hr_continue_session')
      if (!raw) return
      const data = JSON.parse(raw)
      sessionStorage.removeItem('hr_continue_session')
      if (data?.session_id) {
        setSessionId(data.session_id)
        setHistory(data.history || [])
        setCandidateName(data.candidate_name || '')
        setAnalysis(data.analysis || null)
        setEntryMode(data.analysis ? 'analysis' : 'quick')
        setPanelFocus(data.session_type || 'panel')
        setStep('interview')
        setTurns((data.history || []).filter((m) => m.role === 'candidate').length)
        setCanDeliberate((data.history || []).some((m) => m.role === 'candidate'))
        setTimerOn(true)
      }
    } catch (_) {}
  }, [])

  // Resume pure-interview session started from Interviews hub
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('hr_quick_session')
      if (!raw) return
      const data = JSON.parse(raw)
      sessionStorage.removeItem('hr_quick_session')
      if (data?.session_id) {
        setSessionId(data.session_id)
        setHistory(data.history || [])
        setCandidateName(data.candidate_name || '')
        setEntryMode(data.analysis ? 'analysis' : 'quick')
        setAnalysis(data.analysis || null)
        setPanelFocus(data.session_type || 'panel')
        setStep('interview')
        setTurns(0)
        setCanDeliberate(false)
        setTimerSec(0)
        setTimerOn(true)
        setDeliberation(null)
      }
    } catch (_) {}
  }, [])

  // Standalone debug / coding round from Interviews hub
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('hr_coding_session')
      if (!raw) return
      const data = JSON.parse(raw)
      sessionStorage.removeItem('hr_coding_session')
      if (data?.picker && data?.mode) {
        setSessionId(data.session_id || null)
        setCodingMode(data.mode === 'debug' ? 'debug' : 'code')
        setEntryMode(data.mode === 'debug' ? 'debug' : 'coding')
        setCodingPicker({ mode: data.mode === 'debug' ? 'debug' : 'code' })
        setStep('coding-setup')  // never show resume analyzer
        return
      }
      if (data?.session_id && data?.problem) {
        setSessionId(data.session_id)
        setCodingMode(data.mode === 'debug' ? 'debug' : 'code')
        setCodingProblem(data.problem)
        setCodingSubmission(
          data.mode === 'debug'
            ? (data.problem.buggy_code || '')
            : (data.problem.starter || '')
        )
        setCodingReview(null)
        setEntryMode(data.mode === 'debug' ? 'debug' : 'coding')
        setStep('coding')
      }
    } catch (_) {}
  }, [])


  const recognitionRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  useEffect(() => {
    if (!timerOn) {
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }
    timerRef.current = setInterval(() => {
      setTimerSec((s) => s + 1)
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [timerOn])

  useEffect(() => {
    if (!pressureMode || step !== 'interview') {
      if (answerTimerRef.current) clearInterval(answerTimerRef.current)
      return
    }
    answerTimerRef.current = setInterval(() => {
      setAnswerTimer((tm) => (tm <= 0 ? 0 : tm - 1))
    }, 1000)
    return () => clearInterval(answerTimerRef.current)
  }, [pressureMode, step, history])

  async function analyze() {
    setError('')
    setLoading(true)
    try {
      let data
      if (useText) {
        const res = await authFetch(`${API}/analyze/text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            resume_text: resumeText,
            job_description: jd,
            candidate_name: candidateName,
            language: lang,
          }),
        })
        if (!res.ok) throw new Error((await res.json()).detail || t('analysisFailed'))
        data = await res.json()
      } else {
        if (!resumeFile) throw new Error(t('pleaseUploadResume'))
        if (!jd.trim()) throw new Error(t('pleasePasteJd'))
        const fd = new FormData()
        fd.append('resume', resumeFile)
        fd.append('job_description', jd)
        fd.append('candidate_name', candidateName)
        fd.append('language', lang)
        const res = await authFetch(`${API}/analyze`, { method: 'POST', body: fd })
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || t('analysisFailed'))
        }
        data = await res.json()
      }
      setSessionId(data.session_id)
      setAnalysis(data.analysis)
      setResources(data.resources || [])
      setEntryMode('analysis')
      setStep('analysis')
    } catch (e) {
      setError(e.message || t('errorGeneric'))
    } finally {
      setLoading(false)
    }
  }

  function openCodingPicker(mode) {
    setError('')
    const m = typeof mode === 'string' ? mode : (codingMode || 'debug')
    setCodingMode(m)
    setCodingPicker({ mode: m })
    // keep previous difficulty/language so user can change
  }

  async function confirmCodingStart() {
    if (!codingPicker) return
    const mode = codingPicker.mode
    const diff = codingDifficulty
    setError('')
    setLoading(true)
    setCodingReview(null)
    try {
      const res = await authFetch(`${API}/coding/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId || undefined,
          mode,
          difficulty: diff,
          exclude_ids: usedCodingIds,
          language: codingLanguage,
          ui_language: lang,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || t('couldNotStartCoding'))
      }
      const data = await res.json()
      setCodingMode(data.mode)
      setCodingProblem(data.problem)
      setCodingSubmission(data.problem?.buggy_code || data.problem?.starter || '')
      if (data.problem?.id) {
        setUsedCodingIds((prev) => (prev.includes(data.problem.id) ? prev : [...prev, data.problem.id]))
      }
      if (data.session_id) setSessionId(data.session_id)
      setEntryMode(mode === 'debug' ? 'debug' : 'coding')
      setCodingPicker(null)
      setStep('coding')
    } catch (e) {
      setError(typeof e.message === 'string' ? e.message : t('couldNotStartCoding'))
    } finally {
      setLoading(false)
    }
  }

  async function startCoding(mode) {
    openCodingPicker(mode)
  }

  async function submitCoding() {
    if (!sessionId || !codingProblem) return
    setError('')
    setLoading(true)
    try {
      const res = await authFetch(`${API}/coding/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          mode: codingMode,
          problem_id: codingProblem.id,
          problem: codingProblem,
          submission: codingSubmission,
          language: lang,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || t('reviewFailed'))
      const data = await res.json()
      setCodingReview(data.review)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function startDemo() {
    setError('')
    setLoading(true)
    try {
      const res = await authFetch(`${API}/demo/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: lang }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || t('demoFailed'))
      const data = await res.json()
      setSessionId(data.session_id)
      setAnalysis(data.analysis)
      setResources(data.resources || [])
      setCandidateName(data.candidate_name || 'Ananya Rao')
      setSampleAnswers(data.sample_answers || [])
      setJd(data.job_description || '')
      setStep('analysis')
    } catch (e) {
      setError(e.message || t('demoFailed'))
    } finally {
      setLoading(false)
    }
  }

  function fillSampleAnswer() {
    if (!sampleAnswers.length) return
    const next = sampleAnswers[Math.min(turns, sampleAnswers.length - 1)]
    setAnswer(next)
  }

  function printReport() {
    window.print()
  }

  async function copySummary() {
    if (!deliberation) return
    const c = deliberation.consensus || {}
    const stars = history.filter((m) => m.role === 'candidate' && m.star).map((m) => m.star.score)
    const avg = stars.length ? Math.round(stars.reduce((a, b) => a + b, 0) / stars.length) : '—'
    const lines = [
      t('feedbackSummaryTitle'),
      `${t('candidateLabel')}: ${candidateName || t('candidateLabel')}`,
      `${t('verdictLabel')}: ${(c.verdict || '').replace('_', ' ')} · ${t('score')} ${c.score ?? '—'}`,
      `${t('starAverageLabel')}: ${avg}`,
      `${t('keyDisagreementLabel')}: ${c.key_disagreement || '—'}`,
      `${t('recommendationLabel')}: ${c.recommendation || '—'}`,
      mentorNote ? `${t('mentorNoteLabel')}: ${mentorNote}` : '',
      '',
      t('stillWantsKnow'),
      ...((deliberation.follow_up_questions || []).map((q, i) => `${i + 1}. ${q}`)),
      '',
      t('resourcesLabel'),
      ...((resources || []).slice(0, 5).map((r) => `- ${r.title}: ${r.url}`)),
    ]
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setError('')
      alert(t('feedbackCopied'))
    } catch {
      setError(t('couldNotCopy'))
    }
  }

  async function startInterview() {
    setError('')
    setLoading(true)
    setDeliberation(null)
    try {
      const res = await authFetch(`${API}/interview/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          language: lang,
          role: role === 'custom' ? (customRole.trim() || 'professional') : role,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || t('couldNotStartInterview'))
      const data = await res.json()
      setStep('interview')
      setTurns(0)
      setCanDeliberate(false)
      setTimerSec(0)
      setTimerOn(true)
      setHistory([])
      await new Promise((r) => setTimeout(r, 1200))
      setHistory(data.history || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function submitAnswer() {
    if (!answer.trim()) return
    setError('')
    setLoading(true)
    const currentAnswer = answer
    setAnswer('')

    await new Promise((r) => setTimeout(r, 1800))

    try {
      const res = await authFetch(`${API}/interview/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, answer: currentAnswer, language: lang }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || t('failedToSubmit'))
      const data = await res.json()

      const hist = data.history || []
      const withoutLatestPanel = hist.slice(0, -1)
      setHistory(withoutLatestPanel.length ? withoutLatestPanel : hist)
      setTurns(data.turns || 0)
      setCanDeliberate(!!data.can_deliberate)

      await new Promise((r) => setTimeout(r, 2500))
      setHistory(hist)
      if (pressureMode) setAnswerTimer(90)
    } catch (e) {
      setError(e.message)
      setAnswer(currentAnswer)
    } finally {
      setLoading(false)
    }
  }

  async function runDeliberation() {
    setError('')
    setLoading(true)
    try {
      const res = await authFetch(`${API}/interview/deliberate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, language: lang }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || t('deliberationFailed'))
      const data = await res.json()
      setDeliberation(data.deliberation)
      setResources(data.resources || [])
      setMentorNote(data.mentor_note || '')
      setStarAvg(data.star_avg ?? null)
      setStep('deliberation')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function toggleVoice() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      setError(t('speechNotSupported'))
      return
    }
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop()
      setListening(false)
      return
    }
    const rec = new SR()
    recognitionRef.current = rec
    rec.continuous = false
    rec.interimResults = true
    rec.lang = speechLang(lang)
    rec.onresult = (ev) => {
      let text = ''
      for (let i = 0; i < ev.results.length; i++) {
        text += ev.results[i][0].transcript
      }
      setAnswer(text)
    }
    rec.onerror = () => setListening(false)
    rec.onend = () => setListening(false)
    rec.start()
    setListening(true)
  }

  function resetAll() {
    setEntryMode('home')
    setPanelFocus('panel')
    setStep('home')
    setSessionId(null)
    setAnalysis(null)
    setHistory([])
    setDeliberation(null)
    setResources([])
    setAnswer('')
    setError('')
    setTurns(0)
    setSampleAnswers([])
    setTimerSec(0)
    setTimerOn(false)
    setMentorNote('')
    setStarAvg(null)
    setReturnerMode(false)
    setCodingMode(null)
    setCodingProblem(null)
    setCodingSubmission('')
    setCodingReview(null)
    setUsedCodingIds([])
    setCodingDifficulty('easy')
    setCodingPicker(null)
    setCodingLanguage('python')
  }

  function goBack() {
    setError('')
    // Close coding difficulty picker without leaving the page
    if (codingPicker) {
      setCodingPicker(null)
      if (codingProblem) {
        setStep('coding')
        return
      }
      if (step === 'coding-setup') {
        resetAll()
        if (embed && navigate) navigate('/app/interviews')
        return
      }
      // resume flow: picker closed, stay on analysis
      if (analysis) {
        setStep('analysis')
        return
      }
    }
    // Pure interview / standalone coding
    if (entryMode === 'quick' || entryMode === 'coding' || entryMode === 'debug' || step === 'coding-setup') {
      if (step === 'deliberation') {
        setStep('interview')
        return
      }
      resetAll()
      if (embed && navigate) navigate('/app/interviews')
      return
    }
    // Resume+JD flow
    if (step === 'analysis') {
      setStep('home')
      if (embed && navigate) navigate('/app/resume')
    } else if (step === 'interview') {
      setStep(analysis ? 'analysis' : 'home')
    } else if (step === 'coding') {
      setStep(analysis ? 'analysis' : 'home')
    } else if (step === 'deliberation') {
      setStep('interview')
    } else {
      setStep('home')
    }
  }

  async function restartInterview() {
    setError('')
    setAnswer('')
    setHistory([])
    setDeliberation(null)
    setTurns(0)
    setCanDeliberate(false)
    setMentorNote('')
    setStarAvg(null)
    setCodingReview(null)
    if (entryMode === 'quick' || (!analysis && sessionId)) {
      // Restart pure panel with same focus type
      setLoading(true)
      try {
        const focus = entryMode === 'quick' ? 'panel' : 'panel'
        const res = await authFetch(`${API}/interview/quick-start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: lang, role, focus, candidate_name: candidateName }),
        })
        if (!res.ok) throw new Error(t('errorGeneric'))
        const data = await res.json()
        setSessionId(data.session_id)
        setHistory(data.history || [])
        setEntryMode(data.analysis ? 'analysis' : 'quick')
        setAnalysis(data.analysis || null)
        setPanelFocus(data.session_type || 'panel')
        setStep('interview')
        setTimerSec(0)
        setTimerOn(true)
      } catch (e) {
        setError(e.message || t('errorGeneric'))
      } finally {
        setLoading(false)
      }
      return
    }
    if (sessionId && analysis) {
      // restart from existing session
      try {
        setLoading(true)
        const res = await authFetch(`${API}/interview/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            language: lang,
            role: role === 'custom' ? (customRole.trim() || 'professional') : role,
          }),
        })
        if (!res.ok) throw new Error(t('errorGeneric'))
        const data = await res.json()
        setHistory(data.history || [])
        setStep('interview')
        setTimerSec(0)
        setTimerOn(true)
      } catch (e) {
        setError(e.message || t('errorGeneric'))
      } finally {
        setLoading(false)
      }
    }
  }

  async function nextCodingProblem(modeOverride) {
    const raw = modeOverride
    const mode = (typeof raw === 'string' && raw) ? raw : (codingMode || 'debug')
    setCodingMode(mode)
    setCodingReview(null)
    setCodingPicker({ mode })
  }

  function difficultyLabel(d) {
    const key = String(d || '').toLowerCase()
    if (key === 'easy') return t('diffEasy') || 'easy'
    if (key === 'medium') return t('diffMedium') || 'medium'
    if (key === 'hard') return t('diffHard') || 'hard'
    return d
  }

  const statusLabel = (s) => {
    if (s === 'strong') return t('statusStrong')
    if (s === 'partial') return t('statusPartial')
    if (s === 'missing') return t('statusMissing')
    return s
  }

  const verdictLabel = (v) => {
    const key = String(v || '').toLowerCase().replace(/\s+/g, '_')
    if (key === 'hold') return t('verdictHold')
    if (key === 'advance') return t('verdictAdvance')
    if (key === 'reject') return t('verdictReject')
    if (key === 'lean_advance' || key === 'lean advance') return t('verdictAdvance')
    return (v || '').replace(/_/g, ' ')
  }

  return (
    <div className={embed ? 'app-shell embed' : 'app-shell'} lang={lang}>
      {!embed && (
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">TH</div>
          <div>
            <h1>{t('appName')}</h1>
            <p>{t('tagline')}</p>
          </div>
        </div>
        <div className="badge-row" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="pill accent">{t('badgeGirlGeeks')}</span>
          <span className="pill">{t('badgePanel')}</span>
          <LanguageSelector lang={lang} setLang={setLang} />
        </div>
        {step !== 'home' && (
          <button type="button" className="btn btn-ghost btn-back" onClick={goBack}>
            {t('back')}
          </button>
        )}
      </header>
      )}
      {embed && step !== 'home' && (
        <div style={{ marginBottom: 12 }}>
          <button type="button" className="btn btn-ghost btn-back" onClick={goBack}>
            {t('back')}
          </button>
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {step === 'home' && !codingPicker && (
        <>
          <section className="hero">
            <div className="hero-kicker">
              <Sparkles size={14} /> {t('heroKicker')}
            </div>
            <h2>{t('heroTitle')}</h2>
            <p className="hero-sub">{t('heroSub')}</p>
            <div className="persona-strip">
              <div className="persona-chip"><span className="dot hr" /> {t('personaHr')}</div>
              <div className="persona-chip"><span className="dot tech" /> {t('personaTech')}</div>
              <div className="persona-chip"><span className="dot hm" /> {t('personaHm')}</div>
            </div>
          </section>

          <div className="grid-2">
            <div className="card">
              <div className="card-title">{t('cardResumeTitle')}</div>
              <p className="card-sub">{t('cardResumeSub')}</p>

              <div className="field">
                <label>{t('labelName')}</label>
                <input
                  type="text"
                  placeholder={t('placeholderName')}
                  value={candidateName}
                  onChange={(e) => setCandidateName(e.target.value)}
                />
              </div>

              <div className="field">
                <label>
                  {t('labelResume')}{' '}
                  <button
                    type="button"
                    className="btn btn-ghost"
                    style={{ padding: '2px 8px', fontSize: '0.75rem', marginLeft: 8 }}
                    onClick={() => setUseText((v) => !v)}
                  >
                    {useText ? t('switchToFile') : t('pasteTextInstead')}
                  </button>
                </label>
                {useText ? (
                  <textarea
                    placeholder={t('placeholderResumeText')}
                    value={resumeText}
                    onChange={(e) => setResumeText(e.target.value)}
                  />
                ) : (
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc,.txt"
                    onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                  />
                )}
              </div>

              <div className="field">
                <label>{t('labelJd')}</label>
                <textarea
                  placeholder={t('placeholderJd')}
                  value={jd}
                  onChange={(e) => setJd(e.target.value)}
                />
              </div>

              <div className="field">
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" checked={returnerMode} onChange={(e) => setReturnerMode(e.target.checked)} />
                  {t('returnerMode')}
                </label>
              </div>
              <div className="field">
                <label>{t('labelRole')}</label>
                <select value={role} onChange={(e) => setRole(e.target.value)} style={{ width: '100%', padding: '10px 12px', borderRadius: 10, background: 'var(--bg-soft)', border: '1px solid var(--border)', color: 'var(--text)' }}>
                  <option value="data analyst">{t('roleDataAnalyst') || 'Data Analyst'}</option>
                  <option value="data scientist">{t('roleDataScientist') || 'Data Scientist'}</option>
                  <option value="business analyst">{t('roleBizAnalyst') || 'Business Analyst'}</option>
                  <option value="sde">{t('roleSde')}</option>
                  <option value="backend">{t('roleBackend') || 'Backend'}</option>
                  <option value="frontend">{t('roleFrontend') || 'Frontend'}</option>
                  <option value="fullstack">{t('roleFullstack') || 'Full-stack'}</option>
                  <option value="product">{t('roleProduct')}</option>
                  <option value="ml engineer">{t('roleMl') || 'ML Engineer'}</option>
                  <option value="internship">{t('roleInternship')}</option>
                  <option value="custom">{t('roleCustom') || 'Custom…'}</option>
                </select>
                {role === 'custom' && (
                  <input value={customRole} onChange={(e) => setCustomRole(e.target.value)} placeholder={t('roleCustomPlaceholder') || 'e.g. Marketing Analyst'} style={{ width: '100%', marginTop: 8, padding: '10px 12px', borderRadius: 10, background: 'var(--bg-soft)', border: '1px solid var(--border)', color: 'var(--text)' }} />
                )}
              </div>

              <button className="btn btn-primary" disabled={loading} onClick={analyze}>
                {loading ? (
                  <span className="loading"><span className="spinner" /> {t('analyzing')}</span>
                ) : (
                  <><Upload size={18} /> {t('btnAnalyze')}</>
                )}
              </button>
              <button className="btn btn-ghost" style={{ marginTop: 10, width: '100%' }} disabled={loading} onClick={startDemo}>
                <Play size={16} /> {t('btnDemo')}
              </button>
            </div>

            <div className="card">
              <div className="card-title">{t('cardDiffTitle')}</div>
              <p className="card-sub">{t('cardDiffSub')}</p>
              <div className="panelist hr">
                <div className="avatar">HR</div>
                <div>
                  <strong>{t('featurePersonasTitle')}</strong>
                  <span>{t('featurePersonasDesc')}</span>
                </div>
              </div>
              <div className="panelist tech">
                <div className="avatar">TL</div>
                <div>
                  <strong>{t('featureDelibTitle')}</strong>
                  <span>{t('featureDelibDesc')}</span>
                </div>
              </div>
              <div className="panelist hm">
                <div className="avatar">HM</div>
                <div>
                  <strong>{t('featureStarTitle')}</strong>
                  <span>{t('featureStarDesc')}</span>
                </div>
              </div>
              <div className="panelist" style={{ borderStyle: 'dashed' }}>
                <div className="avatar" style={{ background: 'rgba(184,121,31,0.14)', color: '#B8791F' }}>
                  <Target size={16} />
                </div>
                <div>
                  <strong>{t('featureJdTitle')}</strong>
                  <span>{t('featureJdDesc')}</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {step === 'analysis' && analysis && (
        <section>
          <div className="card" style={{ marginBottom: 18 }}>
            <div className="score-ring-wrap">
              <ScoreRing score={analysis.overall_score} />
              <div className="score-meta">
                <h3>{t('matchScoreOf', { score: analysis.overall_score })}</h3>
                <p>{analysis.summary}</p>
                <div className="btn-row" style={{ marginTop: 14 }}>
                  <button className="btn btn-primary" onClick={startInterview} disabled={loading}>
                    {loading ? <span className="loading"><span className="spinner" /> {t('openingPanel')}</span> : <><Users size={18} /> {t('enterHiringRoom')}</>}
                  </button>
                  <button className="btn btn-ghost" onClick={() => openCodingPicker('debug')} disabled={loading}>
                    <Bug size={16} /> {t('debugSnippet')}
                  </button>
                  <button className="btn btn-ghost" onClick={() => openCodingPicker('code')} disabled={loading}>
                    <Code2 size={16} /> {t('miniCoding')}
                  </button>
                  <button className="btn btn-ghost" onClick={() => {
                    if (step === 'interview' || step === 'deliberation') restartInterview()
                    else resetAll()
                  }}><RefreshCw size={16} /> {(step === 'interview' || step === 'deliberation') ? (t('restartInterview') || t('startOver')) : t('startOver')}</button>
                </div>
              </div>
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card-title">{t('matchingSkills')}</div>
              <div className="tag-list">
                {(analysis.matching_skills || []).length ? (
                  analysis.matching_skills.map((s) => <span key={s} className="tag match">{s}</span>)
                ) : (
                  <span className="tag">{t('noStrongOverlaps')}</span>
                )}
              </div>
              <div className="card-title" style={{ marginTop: 20 }}>{t('missingSkills')}</div>
              <div className="tag-list">
                {(analysis.missing_skills || []).length ? (
                  analysis.missing_skills.map((s) => <span key={s} className="tag miss">{s}</span>)
                ) : (
                  <span className="tag match">{t('noneFlagged')}</span>
                )}
              </div>
              <div className="card-title" style={{ marginTop: 20 }}>{t('areasToImprove')}</div>
              <ul style={{ color: 'var(--text-muted)', fontSize: '0.9rem', paddingLeft: 18 }}>
                {(analysis.areas_to_improve || []).map((a, i) => <li key={i} style={{ marginBottom: 6 }}>{a}</li>)}
              </ul>
            </div>

            <div className="card">
              <div className="card-title">{t('perRequirementGaps')}</div>
              <p className="card-sub">{t('perRequirementSub')}</p>
              {(analysis.gaps || []).slice(0, 8).map((g, i) => (
                <div className="gap-item" key={i}>
                  <div className={`status ${g.status}`}>{statusLabel(g.status)}</div>
                  <p>{g.requirement}</p>
                </div>
              ))}
              {(analysis.ats_flags || []).length > 0 && (
                <>
                  <div className="card-title" style={{ marginTop: 16 }}>{t('atsFlags')}</div>
                  {analysis.ats_flags.map((f, i) => (
                    <div key={i} className={`flag ${f.level}`}>
                      <AlertTriangle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                      {f.message}
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>

          <div className="card" style={{ marginTop: 18 }}>
            <div className="card-title">{t('strengthsPortfolio')}</div>
            <p className="card-sub">{t('strengthsPortfolioSub')}</p>
            <div className="tag-list">
              {(analysis.matching_skills || []).slice(0, 12).map((s) => (
                <span key={s} className="tag match">{s}</span>
              ))}
              {(analysis.matching_skills || []).length === 0 && (
                <span className="tag">{t('addStrongerKeywords')}</span>
              )}
            </div>
            {returnerMode && (
              <p style={{ marginTop: 10, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {t('returnerNote')}
              </p>
            )}
          </div>

          {resources && resources.length > 0 && (
            <div className="card" style={{ marginTop: 18 }}>
              <div className="card-title">{t('learningResources')}</div>
              <p className="card-sub">{t('learningResourcesSub')}</p>
              <div style={{ display: 'grid', gap: 10 }}>
                {resources.map((r, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                    <span className="tag match" style={{ textTransform: 'capitalize' }}>{t('rtype_' + (r.type || 'guide')) || r.type}</span>
                    <div>
                      <a href={r.url} target="_blank" rel="noreferrer" style={{ fontWeight: 600 }}>{r.title}</a>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{r.reason}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 2 }}>{t('skillFocus')}: {r.skill}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {step === 'interview' && (
        <section className="interview-layout">
          <div className="card chat-panel">
            <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span>{t('livePanelInterview')}</span>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span className="pill"><Clock size={12} style={{ marginRight: 4 }} /> {Math.floor(timerSec / 60)}:{String(timerSec % 60).padStart(2, '0')}</span>
                <span className="pill">{t('turn')} {turns}</span>
              </div>
            </div>
            <div className="chat-stream">
              {history.map((m) => {
                if (m.role === 'candidate') {
                  return (
                    <div key={m.id} className="bubble candidate">
                      <div className="bubble-meta">
                        {t('you')}
                        {m.star?.confidence ? (
                          <span style={{ marginLeft: 8, opacity: 0.75 }}>· {t('confidence')} {m.star.confidence}/5</span>
                        ) : null}
                      </div>
                      <p>{m.content}</p>
                      <StarChips star={m.star} t={t} />
                      {m.star?.confidence_tip && (
                        <div style={{ marginTop: 8, padding: '8px 10px', borderRadius: 10, background: 'rgba(184,121,31,0.08)', border: '1px solid rgba(184,121,31,0.25)', fontSize: '0.82rem', color: 'var(--warning)' }}>
                          <strong>{t('confidenceCoach')}:</strong> {m.star.confidence_tip}
                        </div>
                      )}
                      {m.star?.leadership && (
                        <div style={{ marginTop: 8, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          <strong style={{ color: 'var(--hm)' }}>{t('leadershipSignals')}:</strong>{' '}
                          {(m.star.leadership.signals || []).length
                            ? m.star.leadership.signals.join(' · ')
                            : t('noneYet')}
                          {(m.star.leadership.tips || []).slice(0, 1).map((tipItem, i) => (
                            <div key={i} style={{ marginTop: 4, color: 'var(--text-dim)' }}>{t('tip')}: {tipItem}</div>
                          ))}
                        </div>
                      )}
                      {m.rewritten && m.star?.rewrite_mode === 'example' && (
                        <div className="rewrite-box" style={{ marginTop: 10 }}>
                          <h4>{t('answerArenaStrong')}</h4>
                          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 2, marginBottom: 8 }}>
                            {t('answerTooShort')}
                          </p>
                          <div style={{ padding: 10, borderRadius: 10, background: 'rgba(21,138,94,0.08)', border: '1px solid rgba(21,138,94,0.25)', fontSize: '0.85rem' }}>
                            <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--success)', marginBottom: 6 }}>{t('exampleAnswer')}</div>
                            {m.rewritten}
                          </div>
                        </div>
                      )}
                      {m.rewritten && m.star?.rewrite_mode !== 'example' && (
                        <div className="rewrite-box" style={{ marginTop: 10 }}>
                          <h4>{t('answerArenaBetter')}</h4>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 8 }}>
                            <div style={{ padding: 10, borderRadius: 10, background: 'rgba(21,27,41,0.05)', fontSize: '0.85rem' }}>
                              <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', marginBottom: 6 }}>{t('original')}</div>
                              {m.content}
                            </div>
                            <div style={{ padding: 10, borderRadius: 10, background: 'rgba(21,138,94,0.08)', border: '1px solid rgba(21,138,94,0.25)', fontSize: '0.85rem' }}>
                              <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--success)', marginBottom: 6 }}>{t('betterYouLabel')}</div>
                              {m.rewritten}
                            </div>
                          </div>
                          {(m.star?.improvements || []).length > 0 && (
                            <ul style={{ marginTop: 8, paddingLeft: 16, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                              {m.star.improvements.map((b, i) => <li key={i}>{b}</li>)}
                            </ul>
                          )}
                        </div>
                      )}
                    </div>
                  )
                }
                const meta = personaMeta[m.persona] || personaMeta[m.role] || { label: m.role, className: '' }
                return (
                  <div key={m.id} className={`bubble ${meta.className || m.role}`}>
                    <div className="bubble-meta">
                      <span className="dot" style={{ background: meta.color || '#8790A0' }} />
                      {meta.label}
                    </div>
                    <p>{m.content}</p>
                  </div>
                )
              })}
              <div ref={chatEndRef} />
            </div>

            <div className="answer-box">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <label style={{ margin: 0 }}>{t('yourAnswer')}</label>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <input type="checkbox" checked={pressureMode} onChange={(e) => { setPressureMode(e.target.checked); setAnswerTimer(90) }} />
                    {t('pressureMode')}
                  </label>
                  {pressureMode && (
                    <span className="pill" style={{ color: answerTimer <= 15 ? 'var(--danger)' : 'var(--text)' }}>
                      {answerTimer}{t('sLeft')}
                    </span>
                  )}
                </div>
              </div>
              <textarea
                placeholder={t('placeholderAnswer')}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submitAnswer()
                }}
              />
              <div className="btn-row">
                <button className="btn btn-primary" disabled={loading || !answer.trim()} onClick={submitAnswer}>
                  {loading ? <span className="loading"><span className="spinner" /> {t('panelResponding')}</span> : <><Send size={16} /> {t('sendAnswer')}</>}
                </button>
                <button className={`btn btn-ghost ${listening ? 'accent' : ''}`} type="button" onClick={toggleVoice}>
                  <Mic size={16} /> {listening ? t('listening') : t('voice')}
                </button>
                {sampleAnswers.length > 0 && (
                  <button className="btn btn-ghost" type="button" onClick={fillSampleAnswer} title={t('sampleAnswer')}>
                    {t('sampleAnswer')}
                  </button>
                )}
                <button
                  className="btn btn-success"
                  disabled={loading || !canDeliberate}
                  onClick={runDeliberation}
                  title={canDeliberate ? t('endInterviewHint') : t('canDeliberateHint')}
                >
                  <Scale size={16} /> {t('endDeliberate')}
                </button>
              </div>
            </div>
          </div>

          <div className="card side-card">
            <h3>{t('thePanel')}</h3>
            {(panelFocus === 'panel' || panelFocus === 'behavioral' || panelFocus === 'hr') && (
            <div className="panelist hr">
              <div className="avatar">HR</div>
              <div>
                <strong>{t('personaHrShort')}</strong>
                <span>{t('hrFocus')}</span>
              </div>
            </div>
            )}
            {(panelFocus === 'panel' || panelFocus === 'technical' || panelFocus === 'tech' || panelFocus === 'tech_lead') && (
            <div className="panelist tech">
              <div className="avatar">TL</div>
              <div>
                <strong>{t('personaTechShort')}</strong>
                <span>{t('depthCorrectness')}</span>
              </div>
            </div>
            )}
            {(panelFocus === 'panel' || panelFocus === 'hiring_manager' || panelFocus === 'hm') && (
            <div className="panelist hm">
              <div className="avatar">HM</div>
              <div>
                <strong>{t('personaHmShort')}</strong>
                <span>{t('impactOwnership')}</span>
              </div>
            </div>
            )}

            <h3 style={{ marginTop: 20 }}>{t('starProgress')}</h3>
            <div style={{ marginBottom: 14 }}>
              {history.filter((m) => m.role === 'candidate' && m.star).length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{t('answerQuestionsHint')}</p>
              ) : (
                history.filter((m) => m.role === 'candidate' && m.star).map((m, i) => {
                  const sc = m.star?.score ?? 0
                  return (
                    <div key={m.id || i} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        <span>{t('answerN', { n: i + 1 })}</span>
                        <span>{sc}/100</span>
                      </div>
                      <div style={{ height: 8, borderRadius: 99, background: 'var(--bg-soft)', overflow: 'hidden' }}>
                        <div style={{ width: `${sc}%`, height: '100%', background: sc >= 70 ? 'var(--success)' : sc >= 45 ? 'var(--warning)' : 'var(--danger)', borderRadius: 99 }} />
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            <h3 style={{ marginTop: 12 }}>{t('sessionSummary')}</h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: 10 }}>
              {(() => {
                const ans = history.filter((m) => m.role === 'candidate')
                const stars = ans.map((m) => m.star?.score).filter((x) => typeof x === 'number')
                const avg = stars.length ? Math.round(stars.reduce((a, b) => a + b, 0) / stars.length) : null
                return t('answersStarAvg', {
                  count: ans.length,
                  s: ans.length === 1 ? '' : 's',
                  avg: avg ?? '—',
                  status: canDeliberate ? t('readyToDeliberate') : t('keepGoing'),
                })
              })()}
            </p>
            <h3 style={{ marginTop: 12 }}>{t('sessionSummary')}</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 12 }}>
              {panelFocus === 'behavioral' || panelFocus === 'hr'
                ? t('sessionHelpHr')
                : panelFocus === 'technical' || panelFocus === 'tech' || panelFocus === 'tech_lead'
                  ? t('sessionHelpTech')
                  : panelFocus === 'hiring_manager' || panelFocus === 'hm'
                    ? t('sessionHelpHm')
                    : t('sessionHelp')}
            </p>
            <button className="btn btn-ghost" style={{ width: '100%', marginBottom: 8 }} onClick={() => startCoding('debug')} disabled={loading}>
              <Bug size={14} /> {t('techRoundDebug')}
            </button>
            <button className="btn btn-ghost" style={{ width: '100%', marginBottom: 8 }} onClick={() => startCoding('code')} disabled={loading}>
              <Code2 size={14} /> {t('techRoundCode')}
            </button>
            <button className="btn btn-ghost" style={{ width: '100%' }} onClick={() => { resetAll(); if (embed && navigate) navigate('/app/interviews') }}>
              <RefreshCw size={14} /> {t('exitSession')}
            </button>
          </div>
        </section>
      )}

      {codingPicker && (
        <div className="card" style={{ marginBottom: 18, padding: 0, overflow: 'hidden' }}>
          <div className={`mode-banner ${codingPicker.mode === 'debug' ? 'debug' : 'code'}`}>
            <div className="mode-banner-icon">
              {codingPicker.mode === 'debug' ? <Bug size={20} /> : <Code2 size={20} />}
            </div>
            <div>
              <div className="mode-banner-title">{codingPicker.mode === 'debug' ? t('debugRound') : t('codingRoundTitle')}</div>
              <div className="mode-banner-sub">
                {codingPicker.mode === 'debug' ? t('debugRoundSub') : t('codingRoundSub')}
              </div>
            </div>
          </div>
          <div style={{ padding: 22 }}>
          <p className="card-sub">{t('selectDifficultyLang')}</p>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 6 }}>{t('difficulty')}</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
            {['easy', 'medium', 'hard'].map((d) => (
              <button
                key={d}
                type="button"
                className="btn btn-ghost"
                style={{
                  borderColor: codingDifficulty === d ? 'var(--accent)' : undefined,
                  color: codingDifficulty === d ? 'var(--accent)' : undefined,
                  fontWeight: codingDifficulty === d ? 700 : 500,
                }}
                onClick={() => setCodingDifficulty(d)}
              >
                {difficultyLabel(d)}
              </button>
            ))}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 6 }}>{t('languageLabel')}</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
            {[
              ['python', 'python'],
              ['javascript', 'javascript'],
              ['java', 'java'],
              ['cpp', 'cpp'],
            ].map(([id, key]) => (
              <button
                key={id}
                type="button"
                className="btn btn-ghost"
                style={{
                  borderColor: codingLanguage === id ? 'var(--accent)' : undefined,
                  color: codingLanguage === id ? 'var(--accent)' : undefined,
                  fontWeight: codingLanguage === id ? 700 : 500,
                }}
                onClick={() => setCodingLanguage(id)}
              >
                {t(key)}
              </button>
            ))}
          </div>
          <div className="btn-row">
            <button className="btn btn-primary" disabled={loading} onClick={confirmCodingStart}>
              {loading ? <span className="loading"><span className="spinner" /> {t('loading')}</span> : t('startThisQuestion')}
            </button>
            <button className="btn btn-ghost" onClick={() => setCodingPicker(null)}>{t('cancel')}</button>
          </div>
          {usedCodingIds.length > 0 && (
            <p style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: 10 }}>
              {t('alreadyUsedSession', { ids: usedCodingIds.join(', ') })}
            </p>
          )}
          </div>
        </div>
      )}

      {step === 'coding' && codingProblem && (
        <section>
          <div className="card" style={{ marginBottom: 16, padding: 0, overflow: 'hidden' }}>
            <div className={`mode-banner ${codingMode === 'debug' ? 'debug' : 'code'}`}>
              <div className="mode-banner-icon">
                {codingMode === 'debug' ? <Bug size={20} /> : <Code2 size={20} />}
              </div>
              <div>
                <div className="mode-banner-title">{codingMode === 'debug' ? t('debugRound') : t('codingRoundTitle')}</div>
                <div className="mode-banner-sub">Tech Lead · {difficultyLabel(codingProblem.difficulty)} · {codingProblem.language}</div>
              </div>
            </div>
            <div style={{ padding: 22 }}>
            <p className="card-sub">{codingProblem.title}</p>
            <p style={{ marginBottom: 12 }}>{codingProblem.prompt}</p>
            {codingProblem.hint && (
              <p style={{ fontSize: '0.85rem', color: 'var(--warning)', marginBottom: 12 }}>{t('hint')}: {codingProblem.hint}</p>
            )}
            <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{t('yourSolution')}</label>
            <textarea
              className="code-editor"
              style={{ minHeight: 260, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.85rem', tabSize: 4, whiteSpace: 'pre', lineHeight: 1.45 }}
              value={codingSubmission}
              onChange={(e) => setCodingSubmission(e.target.value)}
              spellCheck={false}
              onKeyDown={(e) => {
                if (e.key === 'Tab') {
                  e.preventDefault()
                  const el = e.target
                  const start = el.selectionStart
                  const end = el.selectionEnd
                  const val = codingSubmission
                  const insert = '    '
                  const next = val.substring(0, start) + insert + val.substring(end)
                  setCodingSubmission(next)
                  requestAnimationFrame(() => {
                    el.selectionStart = el.selectionEnd = start + insert.length
                  })
                }
              }}
            />
            <div className="btn-row" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" disabled={loading || !codingSubmission.trim()} onClick={submitCoding}>
                {loading ? <span className="loading"><span className="spinner" /> {t('techLeadReviewing')}</span> : <><Code2 size={16} /> {t('submitToTechLead')}</>}
              </button>
              <button className="btn btn-ghost" disabled={loading} onClick={() => nextCodingProblem()}>
                {t('nextQuestion')}
              </button>
              <button className="btn btn-ghost" onClick={goBack}>{t('back')}</button>
              <button className="btn btn-ghost" onClick={startInterview}><Users size={16} /> {t('behavioralPanel')}</button>
            </div>
            {usedCodingIds.length > 0 && (
              <p style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: 8 }}>
                {t('usedThisSessionCount', { count: usedCodingIds.length })}
              </p>
            )}
            </div>
          </div>

          {codingReview && (
            <div className="card">
              <div className="card-title">{t('techLeadReview')}</div>
              <p className="card-sub">{t('staticReview')}</p>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
                <span className="pill accent">{t('score')} {codingReview.score}/100</span>
                <span className="pill">{codingReview.verdict}</span>
                {codingMode === 'debug' && (
                  <span className="pill">{codingReview.bug_identified ? t('bugIdentified') : t('bugUnclear')}</span>
                )}
              </div>
              <p style={{ marginBottom: 10 }}>{codingReview.feedback}</p>
              {(codingReview.strengths || []).length > 0 && (
                <>
                  <div style={{ fontSize: '0.8rem', color: 'var(--success)' }}>{t('strengths')}</div>
                  <ul style={{ paddingLeft: 18, marginBottom: 8 }}>{codingReview.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </>
              )}
              {(codingReview.concerns || []).length > 0 && (
                <>
                  <div style={{ fontSize: '0.8rem', color: 'var(--danger)' }}>{t('concerns')}</div>
                  <ul style={{ paddingLeft: 18, marginBottom: 8 }}>{codingReview.concerns.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </>
              )}
              {codingReview.better_code ? (
                <div className="rewrite-box" style={{ marginTop: 12 }}>
                  <h4>{t('referenceSolution')}</h4>
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.82rem', margin: 0 }}>{codingReview.better_code}</pre>
                </div>
              ) : (
                codingReview.score >= 85 && (
                  <p style={{ marginTop: 12, fontSize: '0.9rem', color: 'var(--success)' }}>
                    {t('noAlternateCode')}
                  </p>
                )
              )}
            </div>
          )}
        </section>
      )}

      {step === 'deliberation' && deliberation && (
        <section>
          <div className="verdict-banner">
            <div className="label">{t('panelConsensus')}</div>
            <h3>
              {verdictLabel(deliberation.consensus?.verdict || 'hold')}
              {typeof deliberation.consensus?.score === 'number' && (
                <span style={{ opacity: 0.7 }}> · {deliberation.consensus.score}/100</span>
              )}
            </h3>
            <p style={{ color: 'var(--text-muted)' }}>{deliberation.consensus?.summary}</p>
            {deliberation.consensus?.key_disagreement && (
              <p style={{ marginTop: 10, fontSize: '0.9rem' }}>
                <strong style={{ color: 'var(--warning)' }}>{t('keyDisagreement')}: </strong>
                {deliberation.consensus.key_disagreement}
              </p>
            )}
            {deliberation.consensus?.recommendation && (
              <p style={{ marginTop: 8, fontSize: '0.9rem' }}>
                <strong>{t('recommendation')}: </strong>
                {deliberation.consensus.recommendation}
              </p>
            )}
          </div>

          <div className="eval-grid">
            {(['hr', 'tech_lead', 'hiring_manager'].filter((key) => deliberation.individual?.[key])).map((key) => {
              const ind = deliberation.individual?.[key]
              if (!ind) return null
              const meta = personaMeta[key]
              return (
                <div className="eval-card" key={key}>
                  <h4 style={{ color: meta.color }}>{meta.label}</h4>
                  <div className="eval-score">{ind.score}</div>
                  <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: 8 }}>
                    {verdictLabel(ind.verdict)}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--success)', marginBottom: 4 }}>{t('strengths')}</div>
                  <ul>
                    {(ind.strengths || []).map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                  <div style={{ fontSize: '0.8rem', color: 'var(--danger)', margin: '8px 0 4px' }}>{t('concerns')}</div>
                  <ul>
                    {(ind.concerns || []).map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )
            })}
          </div>

          <div className="card">
            <div className="card-title">{t('visibleDelibTranscript')}</div>
            <p className="card-sub">{t('visibleDelibSub')}</p>
            {(deliberation.transcript || []).map((line, i) => {
              const sp = (line.speaker || '').toLowerCase()
              let cls = 'hm'
              if (sp.includes('hr')) cls = 'hr'
              else if (sp.includes('tech')) cls = 'tech-lead'
              else if (sp.includes('hiring')) cls = 'hiring-manager'
              return (
                <div className="debate-line" key={i}>
                  <div className={`speaker ${cls}`}>{line.speaker}</div>
                  <div style={{ fontSize: '0.95rem', color: 'var(--text)' }}>{line.text}</div>
                </div>
              )
            })}
          </div>

          {mentorNote && (
            <div className="card" style={{ marginTop: 18, borderColor: 'rgba(109,79,224,0.35)' }}>
              <div className="card-title">{t('mentorNote')}</div>
              <p className="card-sub">{t('mentorNoteSub')}</p>
              <p style={{ fontSize: '0.95rem', lineHeight: 1.6 }}>{mentorNote}</p>
              {starAvg != null && (
                <p style={{ marginTop: 8, fontSize: '0.85rem', color: 'var(--text-muted)' }}>{t('sessionStarAvg', { avg: starAvg })}</p>
              )}
            </div>
          )}

          {(deliberation.follow_up_questions || []).length > 0 && (
            <div className="card" style={{ marginTop: 18 }}>
              <div className="card-title">{t('stillWants')}</div>
              <p className="card-sub">{t('stillWantsSub')}</p>
              <ol style={{ paddingLeft: 18, color: 'var(--text)', fontSize: '0.92rem' }}>
                {deliberation.follow_up_questions.map((q, i) => (
                  <li key={i} style={{ marginBottom: 10 }}>{q}</li>
                ))}
              </ol>
            </div>
          )}

          <div className="card" style={{ marginTop: 18 }}>
            <div className="card-title">{t('starBreakdownPerAnswer')}</div>
            <p className="card-sub">{t('starBreakdownSub')}</p>
            {history.filter((m) => m.role === 'candidate' && m.star).map((m, i, arr) => {
              const sc = m.star?.score ?? 0
              const idxInHistory = history.indexOf(m)
              const askedMsg = [...history.slice(0, idxInHistory)].reverse().find((h) => h.role in personaMeta)
              const isOpen = !!expandedStars[m.id || i]
              return (
                <div key={m.id || i} style={{ marginBottom: 14, paddingBottom: 14, borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    <span>{t('answerN', { n: i + 1 })}{askedMsg ? ` · ${personaMeta[askedMsg.role]?.short}` : ''}</span>
                    <span>{sc}/100</span>
                  </div>
                  {askedMsg?.content && (
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-dim)', margin: '4px 0 6px', fontStyle: 'italic' }}>
                      “{askedMsg.content}”
                    </p>
                  )}
                  <div style={{ height: 10, borderRadius: 99, background: 'var(--bg-soft)', overflow: 'hidden' }}>
                    <div style={{ width: `${sc}%`, height: '100%', background: sc >= 70 ? 'var(--success)' : sc >= 45 ? 'var(--warning)' : 'var(--danger)' }} />
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    style={{ marginTop: 8, padding: '4px 10px', fontSize: '0.75rem' }}
                    onClick={() => setExpandedStars((prev) => ({ ...prev, [m.id || i]: !prev[m.id || i] }))}
                  >
                    {isOpen ? t('hideStarBreakdown') : t('showStarBreakdown')}
                  </button>
                  {isOpen && <StarBreakdown star={m.star} t={t} />}
                </div>
              )
            })}
          </div>

          {resources && resources.length > 0 && (
            <div className="card" style={{ marginTop: 18 }}>
              <div className="card-title">{t('learningResources')}</div>
              <p className="card-sub">{t('learningResourcesDelibSub')}</p>
              <div style={{ display: 'grid', gap: 10 }}>
                {resources.map((r, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                    <span className="tag match" style={{ textTransform: 'capitalize' }}>{t('rtype_' + (r.type || 'guide')) || r.type}</span>
                    <div>
                      <a href={r.url} target="_blank" rel="noreferrer" style={{ fontWeight: 600 }}>{r.title}</a>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{r.reason}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 2 }}>{t('skillFocus')}: {r.skill}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="btn-row section-spacer">
            <button className="btn btn-primary" onClick={printReport}>
              <Download size={16} /> {t('downloadReport')}
            </button>
            <button className="btn btn-ghost" onClick={copySummary}>
              {t('copySummary')}
            </button>
            <button className="btn btn-ghost" onClick={startInterview}>
              <MessageSquare size={16} /> {t('practiceAnother')}
            </button>
            <button className="btn btn-ghost" onClick={() => setStep('analysis')}>
              <FileText size={16} /> {t('backToAnalysis')}
            </button>
            <button className="btn btn-ghost" onClick={() => {
              if (step === 'interview' || step === 'deliberation') restartInterview()
              else { resetAll(); if (embed && navigate) navigate('/app/interviews') }
            }}>
              <RefreshCw size={16} /> {t('newSession')}
            </button>
          </div>
        </section>
      )}

      <p className="footer-note">{t('footer')}</p>
    </div>
  )
}
