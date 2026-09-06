import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Users, Code2, MessageSquare, Briefcase, ArrowRight, Bug, Loader2, FileText } from 'lucide-react'
import { api } from '../api'
import { getStoredLanguage, t } from '../i18n'
import { useAuth } from '../AuthContext'

export default function Interviews({ lang }) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const L = lang || getStoredLanguage()
  const tr = (k, v) => t(k, L, v)
  const [loading, setLoading] = useState(null)
  const [error, setError] = useState('')
  const [role, setRole] = useState(user?.target_role || 'data analyst')
  const [customRole, setCustomRole] = useState('')
  const [useLatest, setUseLatest] = useState(false)
  const [latest, setLatest] = useState(null)

  useEffect(() => {
    let alive = true
    api('/resume/latest')
      .then((d) => { if (alive) setLatest(d) })
      .catch(() => { if (alive) setLatest({ has_analysis: false }) })
    return () => { alive = false }
  }, [])

  async function startQuick(focus) {
    setError('')
    setLoading(focus)
    try {
      const endpoint = useLatest && latest?.has_analysis
        ? '/interview/from-latest'
        : '/interview/quick-start'
      const data = await api(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          language: L,
          role: (role === 'custom' ? (customRole.trim() || 'professional') : role),
          focus,
          candidate_name: user?.full_name || '',
        }),
      })
      sessionStorage.setItem('hr_quick_session', JSON.stringify({
        session_id: data.session_id,
        history: data.history || [],
        candidate_name: data.candidate_name,
        quick: true,
        session_type: data.session_type,
        analysis: data.analysis || null,
      }))
      navigate('/app/workspace?mode=quick')
    } catch (e) {
      setError(e.message || 'Could not start interview')
    } finally {
      setLoading(null)
    }
  }

  function startCoding(mode) {
    // Standalone: only difficulty/language picker + AI problem — no resume analyzer
    sessionStorage.setItem('hr_coding_session', JSON.stringify({
      mode: mode === 'debug' ? 'debug' : 'code',
      picker: true,
      standalone: true,
    }))
    navigate(`/app/workspace?mode=${mode === 'debug' ? 'debug' : 'coding'}`)
  }

  const hasLatest = !!latest?.has_analysis
  const latestLine = hasLatest
    ? tr('lastAnalyzedLine', {
        date: latest.created_at ? new Date(latest.created_at).toLocaleDateString() : '—',
        role: role.toUpperCase(),
        score: latest.overall_score != null ? Math.round(latest.overall_score) : '—',
      })
    : tr('noSavedAnalysis')

  const cards = [
    {
      key: 'panel',
      icon: Users,
      title: 'modePanel',
      desc: 'modePanelDesc',
      tag: 'tagRecommended',
      action: () => startQuick('panel'),
      primary: true,
    },
    {
      key: 'hr',
      icon: MessageSquare,
      title: 'modeHr',
      desc: 'modeHrDesc',
      tag: 'tagSoft',
      action: () => startQuick('hr'),
    },
    {
      key: 'technical',
      icon: Users,
      title: 'modeTech',
      desc: 'modeTechDesc',
      tag: 'tagTechnical',
      action: () => startQuick('technical'),
    },
    {
      key: 'hm',
      icon: Briefcase,
      title: 'modeHm',
      desc: 'modeHmDesc',
      tag: 'tagHm',
      action: () => startQuick('hiring_manager'),
    },
    {
      key: 'debug',
      icon: Bug,
      title: 'modeDebug',
      desc: 'modeDebugDesc',
      tag: 'tagDebug',
      action: () => startCoding('debug'),
      pure: true,
    },
    {
      key: 'code',
      icon: Code2,
      title: 'modeCoding',
      desc: 'modeCodingDesc',
      tag: 'tagCoding',
      action: () => startCoding('code'),
      pure: true,
    },
    {
      key: 'resume',
      icon: FileText,
      title: 'modeResume',
      desc: 'modeResumeDesc',
      tag: 'tagJd',
      link: '/app/resume',
    },
  ]

  return (
    <div className="dash">
      <div className="page-header">
        <div>
          <h1>{tr('interviewsTitle')}</h1>
          <p className="muted">{tr('interviewsSub')}</p>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card" style={{ marginBottom: 18 }}>
        <label style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block', marginBottom: 12 }}>
          {tr('targetRole')}
          <span className="muted" style={{ display: 'block', fontWeight: 400, fontSize: '0.8rem', marginTop: 4 }}>{tr('targetRoleHint')}</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            style={{ display: 'block', marginTop: 8, width: '100%', maxWidth: 420, padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'var(--bg-soft)', color: 'var(--text)' }}
          >
            <option value="data analyst">{tr('roleDataAnalyst')}</option>
            <option value="data scientist">{tr('roleDataScientist')}</option>
            <option value="business analyst">{tr('roleBizAnalyst')}</option>
            <option value="sde">{tr('roleSde')}</option>
            <option value="backend">{tr('roleBackend')}</option>
            <option value="frontend">{tr('roleFrontend')}</option>
            <option value="fullstack">{tr('roleFullstack')}</option>
            <option value="product">{tr('roleProduct')}</option>
            <option value="ml engineer">{tr('roleMl')}</option>
            <option value="internship">{tr('roleInternship')}</option>
            <option value="custom">{tr('roleCustom')}</option>
          </select>
          {role === 'custom' && (
            <input
              value={customRole}
              onChange={(e) => setCustomRole(e.target.value)}
              placeholder={tr('roleCustomPlaceholder')}
              style={{ display: 'block', marginTop: 10, width: '100%', maxWidth: 420, padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'var(--bg-soft)', color: 'var(--text)' }}
            />
          )}
        </label>

        <div style={{
          padding: 14,
          borderRadius: 12,
          border: `1px solid ${useLatest && hasLatest ? 'var(--accent)' : 'var(--border)'}`,
          background: 'var(--bg-soft)',
        }}>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: hasLatest ? 'pointer' : 'not-allowed', opacity: hasLatest ? 1 : 0.7 }}>
            <input
              type="checkbox"
              checked={useLatest && hasLatest}
              disabled={!hasLatest}
              onChange={(e) => setUseLatest(e.target.checked)}
              style={{ marginTop: 3 }}
            />
            <span>
              <strong style={{ display: 'block' }}>{tr('useLastResume')}</strong>
              <span className="muted" style={{ fontSize: '0.85rem' }}>{latestLine}</span>
              {!hasLatest && (
                <span style={{ display: 'block', marginTop: 6 }}>
                  <Link to="/app/resume" className="link-btn">{tr('uploadResumeFirst')}</Link>
                </span>
              )}
            </span>
          </label>
        </div>
        <p className="muted" style={{ fontSize: '0.8rem', marginTop: 10 }}>
          {tr('useLastHint')}
        </p>
      </div>

      <div className="mode-grid">
        {cards.map(({ key, icon: Icon, title, desc, tag, action, link, primary, pure }) => {
          const inner = (
            <>
              <div className="mode-card-top">
                <div className="feature-icon"><Icon size={20} /></div>
                <span className="pill">{tr(tag)}</span>
              </div>
              <h3>{tr(title)}</h3>
              <p>{tr(desc)}</p>
              {pure && <p className="muted" style={{ fontSize: '0.78rem' }}>{tr('pureRoundNote')}</p>}
              <span className="mode-cta">
                {loading === key ? (
                  <><Loader2 size={14} className="spin" /> {tr('starting')}</>
                ) : (
                  <>{tr('enterRoom')} <ArrowRight size={14} /></>
                )}
              </span>
            </>
          )
          if (link) {
            return (
              <Link key={key} to={link} className={`mode-card ${primary ? 'primary' : ''}`}>
                {inner}
              </Link>
            )
          }
          return (
            <button
              key={key}
              type="button"
              className={`mode-card ${primary ? 'primary' : ''}`}
              onClick={action}
              disabled={!!loading}
              style={{ textAlign: 'left', cursor: 'pointer', width: '100%', font: 'inherit', color: 'inherit' }}
            >
              {inner}
            </button>
          )
        })}
      </div>
    </div>
  )
}
