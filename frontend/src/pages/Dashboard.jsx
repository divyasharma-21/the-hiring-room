import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { api } from '../api'
import { t, getStoredLanguage } from '../i18n'
import {
  ArrowRight, FileText, Mic, TrendingUp, Target, Sparkles, Clock
} from 'lucide-react'

function ScorePill({ label, value }) {
  if (value == null) return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value muted">—</div>
    </div>
  )
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{Math.round(value)}<span className="stat-unit">/100</span></div>
    </div>
  )
}

function typeLabel(tr, type) {
  const k = String(type || 'full').toLowerCase()
  const map = {
    full: 'typeFull',
    panel: 'typePanel',
    behavioral: 'typeHr',
    hr: 'typeHr',
    technical: 'typeTech',
    tech: 'typeTech',
    hiring_manager: 'typeHm',
    hm: 'typeHm',
    coding: 'typeCoding',
    debug: 'typeDebug',
  }
  return tr(map[k] || 'typeFull')
}

function statusLabel(tr, status) {
  const k = String(status || '').toLowerCase()
  const map = {
    created: 'statusCreated',
    ready: 'statusReady',
    interviewing: 'statusInterviewing',
    deliberating: 'statusDeliberating',
    complete: 'statusComplete',
  }
  return tr(map[k] || 'statusReady')
}

export default function Dashboard({ lang }) {
  const L = lang || getStoredLanguage()
  const tr = (k, v) => t(k, L, v)
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const d = await api('/dashboard')
        if (alive) setData(d)
      } catch (e) {
        if (alive) setError(e.message)
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false }
  }, [])

  const name = user?.full_name || user?.email?.split('@')[0] || 'there'
  const stats = data?.stats || {}

  return (
    <div className="dash">
      <div className="page-header">
        <div>
          <h1>{tr('welcomeUser', { name })}</h1>
          <p className="muted">
            {stats.interviews_completed > 0 ? tr('dashImproving') : tr('dashFirst')}
          </p>
        </div>
        <Link to="/app/interviews" className="btn btn-primary">
          <Mic size={16} /> {tr('startInterview')} <ArrowRight size={16} />
        </Link>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <div className="skeleton-row"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>}

      {!loading && (
        <>
          <div className="stat-grid">
            <ScorePill label={tr('resumeScore')} value={stats.latest_resume_score ?? stats.avg_resume_score} />
            <ScorePill label={tr('interviewScore')} value={stats.latest_interview_score ?? stats.avg_interview_score} />
            <div className="stat-card">
              <div className="stat-label">{tr('interviewsCompleted')}</div>
              <div className="stat-value">{stats.interviews_completed || 0}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">{tr('sessionsTotal')}</div>
              <div className="stat-value">{stats.sessions_total || 0}</div>
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card-title">{tr('recommended')}</div>
              <div className="rec-list">
                <Link to="/app/interviews" className="rec-item">
                  <Mic size={18} />
                  <div>
                    <strong>{tr('recPanel')}</strong>
                    <span>{tr('recPanelSub')}</span>
                  </div>
                  <ArrowRight size={16} />
                </Link>
                <Link to="/app/resume" className="rec-item">
                  <FileText size={18} />
                  <div>
                    <strong>{tr('recResume')}</strong>
                    <span>{tr('recResumeSub')}</span>
                  </div>
                  <ArrowRight size={16} />
                </Link>
                <Link to="/app/performance" className="rec-item">
                  <TrendingUp size={18} />
                  <div>
                    <strong>{tr('recPerf')}</strong>
                    <span>{tr('recPerfSub')}</span>
                  </div>
                  <ArrowRight size={16} />
                </Link>
              </div>
            </div>

            <div className="card">
              <div className="card-title">{tr('yourSignals')}</div>
              <div className="signal-block">
                <div className="signal-label"><Target size={14} /> {tr('strengths')}</div>
                <div className="tag-list">
                  {(data?.strengths || []).length
                    ? data.strengths.map((s) => <span key={s} className="tag match">{s}</span>)
                    : <span className="muted">{tr('uploadForStrengths')}</span>}
                </div>
              </div>
              <div className="signal-block">
                <div className="signal-label"><Sparkles size={14} /> {tr('areasImprove')}</div>
                <div className="tag-list">
                  {(data?.gaps || []).length
                    ? data.gaps.map((s) => <span key={s} className="tag miss">{s}</span>)
                    : <span className="muted">{tr('gapsAfterJd')}</span>}
                </div>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 18 }}>
            <div className="card-title"><Clock size={16} style={{ marginRight: 8 }} /> {tr('recentActivity')}</div>
            {(data?.recent || []).length === 0 ? (
              <div className="empty-state">
                <p>{tr('noSessionsYet')}</p>
                <p className="muted">{tr('firstWaiting')}</p>
                <Link to="/app/interviews" className="btn btn-primary">{tr('startFirst')}</Link>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{tr('colDate')}</th>
                      <th>{tr('colType')}</th>
                      <th>{tr('colStatus')}</th>
                      <th>{tr('colScore')}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent.map((r) => (
                      <tr key={r.session_id}>
                        <td>{r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}</td>
                        <td>{typeLabel(tr, r.session_type)}</td>
                        <td><span className={`status-pill ${r.status}`}>{statusLabel(tr, r.status)}</span></td>
                        <td>{r.consensus_score != null ? Math.round(r.consensus_score) : '—'}</td>
                        <td>
                          <Link to={`/app/history/${r.session_id}`} className="link-btn">{tr('view')}</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
