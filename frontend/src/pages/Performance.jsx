import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { t, getStoredLanguage } from '../i18n'
import { BarChart3, ArrowRight } from 'lucide-react'

export default function Performance({ lang }) {
  const L = lang || getStoredLanguage()
  const tr = (k) => t(k, L)

  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/dashboard')
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  const stats = data?.stats || {}
  const recent = (data?.recent || []).filter((r) => r.consensus_score != null)

  return (
    <div className="dash">
      <div className="page-header">
        <div>
          <h1>
            <BarChart3 size={22} style={{ marginRight: 8, verticalAlign: 'middle' }} />
            {tr('performanceTitle')}
          </h1>
          <p className="muted">{tr('performanceSub')}</p>
        </div>
      </div>
      {error && <div className="error-box">{error}</div>}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">{tr('avgResume')}</div>
          <div className="stat-value">
            {stats.avg_resume_score != null ? Math.round(stats.avg_resume_score) : '—'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{tr('avgInterview')}</div>
          <div className="stat-value">
            {stats.avg_interview_score != null ? Math.round(stats.avg_interview_score) : '—'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{tr('interviewsCompleted')}</div>
          <div className="stat-value">{stats.interviews_completed || 0}</div>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 18 }}>
        <div className="card">
          <div className="card-title">{tr('strengths')}</div>
          <div className="tag-list">
            {(data?.strengths || []).length
              ? data.strengths.map((s) => <span key={s} className="tag match">{s}</span>)
              : <span className="muted">{tr('uploadForStrengths')}</span>}
          </div>
        </div>
        <div className="card">
          <div className="card-title">{tr('areasImprove')}</div>
          <div className="tag-list">
            {(data?.gaps || []).length
              ? data.gaps.map((s) => <span key={s} className="tag miss">{s}</span>)
              : <span className="muted">{tr('gapsAfterJd')}</span>}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <div className="card-title">{tr('scoreTrend')}</div>
        {recent.length === 0 ? (
          <div className="empty-state">
            <p>{tr('noScored')}</p>
            <Link to="/app/interviews" className="btn btn-primary">
              {tr('takeInterview')} <ArrowRight size={14} />
            </Link>
          </div>
        ) : (
          <div className="bars">
            {recent.slice(0, 8).reverse().map((r) => (
              <div key={r.session_id} className="bar-row">
                <span className="bar-label">
                  {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                </span>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${Math.min(100, r.consensus_score)}%` }}
                  />
                </div>
                <span className="bar-val">{Math.round(r.consensus_score)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
