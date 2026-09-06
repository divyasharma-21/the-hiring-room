import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { t, getStoredLanguage } from '../i18n'
import { History as HistoryIcon, ArrowLeft } from 'lucide-react'


function typeLabel(tr, type) {
  const k = String(type || 'full').toLowerCase()
  const map = {
    full: 'typeFull', panel: 'typePanel', behavioral: 'typeHr', hr: 'typeHr',
    technical: 'typeTech', tech: 'typeTech', coding: 'typeCoding', debug: 'typeDebug',
  }
  return tr(map[k] || 'typeFull')
}
function statusLabel(tr, status) {
  const k = String(status || '').toLowerCase()
  const map = {
    created: 'statusCreated', ready: 'statusReady', interviewing: 'statusInterviewing',
    deliberating: 'statusDeliberating', complete: 'statusComplete',
  }
  return tr(map[k] || 'statusReady')
}

export default function HistoryPage({ lang }) {
  const L = lang || getStoredLanguage()
  const tr = (k) => t(k, L)
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [filter, setFilter] = useState('all')
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const type = filter === 'all' ? undefined : filter
        const q = type ? `?type=${type}` : ''
        const d = await api(`/history${q}`)
        if (alive) setItems(d.items || [])
      } catch (e) {
        if (alive) setError(e.message)
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false }
  }, [filter])

  useEffect(() => {
    if (!sessionId) { setDetail(null); return }
    let alive = true
    ;(async () => {
      try {
        const d = await api(`/session/${sessionId}`)
        if (alive) setDetail(d)
      } catch (e) {
        if (alive) setError(e.message)
      }
    })()
    return () => { alive = false }
  }, [sessionId])

  if (sessionId && detail) {
    return (
      <div className="dash">
        <Link to="/app/history" className="btn btn-ghost" style={{ marginBottom: 16 }}>
          <ArrowLeft size={16} /> {tr('backHistory')}
        </Link>
        <div className="card">
          <div className="card-title">{tr('sessionDetail')}</div>
          <p className="muted">{detail.status} · {detail.candidate_name}</p>
          {detail.analysis?.overall_score != null && (
            <p>{tr('resumeScore')}: <strong>{detail.analysis.overall_score}/100</strong></p>
          )}
          <p className="muted" style={{ marginTop: 12 }}>{tr('messages')}: {(detail.history || []).length}</p>
          <div className="chat-stream" style={{ maxHeight: 420, marginTop: 12 }}>
            {(detail.history || []).map((m) => (
              <div key={m.id} className={`bubble ${m.role === 'candidate' ? 'candidate' : m.role}`}>
                <div className="bubble-meta">{m.persona || m.role}</div>
                <p>{m.content}</p>
              </div>
            ))}
          </div>
          {['created', 'ready', 'interviewing', 'deliberating'].includes(String(detail.status || '').toLowerCase()) ? (
            <button
              type="button"
              className="btn btn-primary"
              style={{ marginTop: 16 }}
              onClick={() => {
                sessionStorage.setItem('hr_continue_session', JSON.stringify({
                  session_id: detail.session_id || sessionId,
                  history: detail.history || [],
                  candidate_name: detail.candidate_name || '',
                  analysis: detail.analysis || null,
                  session_type: detail.session_type || 'panel',
                }))
                navigate('/app/workspace?mode=continue')
              }}
            >
              {tr('continueInterview')}
            </button>
          ) : (
            <Link to="/app/interviews" className="btn btn-primary" style={{ marginTop: 16 }}>{tr('continuePractice')}</Link>
          )}
        </div>
      </div>
    )
  }

  const filters = [
    { id: 'all', key: 'filterAll' },
    { id: 'interviews', key: 'filterInterviews' },
    { id: 'resume', key: 'filterResume' },
    { id: 'coding', key: 'filterCoding' },
    { id: 'debug', key: 'filterDebug' },
  ]

  return (
    <div className="dash">
      <div className="page-header">
        <div>
          <h1><HistoryIcon size={22} style={{ marginRight: 8, verticalAlign: 'middle' }} /> {tr('historyTitle')}</h1>
          <p className="muted">{tr('historySub')}</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ color: 'var(--danger, #b91c1c)' }}
          onClick={async () => {
            if (!window.confirm(tr('clearHistoryConfirm'))) return
            try {
              await api('/history/clear', { method: 'DELETE' })
              setItems([])
              setDetail(null)
              setError('')
            } catch (e) {
              setError(e.message)
            }
          }}
        >
          {tr('clearHistory')}
        </button>
      </div>
      {error && <div className="error-box">{error}</div>}
      <div className="filter-row">
        {filters.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`btn btn-ghost ${filter === f.id ? 'active-filter' : ''}`}
            onClick={() => { setFilter(f.id); setLoading(true) }}
          >
            {tr(f.key)}
          </button>
        ))}
      </div>
      {loading ? (
        <div className="skeleton" style={{ height: 120 }} />
      ) : items.length === 0 ? (
        <div className="empty-state card">
          <p>{tr('noHistory')}</p>
          <p className="muted">{tr('noHistorySub')}</p>
          <Link to="/app/interviews" className="btn btn-primary">{tr('startPracticing')}</Link>
        </div>
      ) : (
        <div className="card table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{tr('colDate')}</th>
                <th>{tr('colActivity')}</th>
                <th>{tr('colType')}</th>
                <th>{tr('colScore')}</th>
                <th>{tr('colStatus')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => {
                const incomplete = ['created', 'ready', 'interviewing', 'deliberating'].includes(String(it.status || '').toLowerCase())
                const isInterview = !['debug', 'coding'].includes(String(it.session_type || '').toLowerCase())
                return (
                <tr key={it.session_id}>
                  <td>{it.created_at ? new Date(it.created_at).toLocaleString() : '—'}</td>
                  <td>{({
                    'Interview': tr('filterInterviews'),
                    'Resume analysis': tr('filterResume'),
                    'Coding round': tr('filterCoding'),
                    'Debug round': tr('filterDebug'),
                  })[it.activity] || it.activity}</td>
                  <td>{typeLabel(tr, it.session_type)}</td>
                  <td>{it.score != null ? Math.round(it.score) : '—'}</td>
                  <td><span className={`status-pill ${it.status}`}>{statusLabel(tr, it.status)}</span></td>
                  <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <Link to={`/app/history/${it.session_id}`} className="link-btn">{tr('open')}</Link>
                    {incomplete && isInterview && (
                      <button
                        type="button"
                        className="link-btn"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent)', fontWeight: 600 }}
                        onClick={async () => {
                          try {
                            const d = await api(`/session/${it.session_id}`)
                            sessionStorage.setItem('hr_continue_session', JSON.stringify({
                              session_id: d.session_id || it.session_id,
                              history: d.history || [],
                              candidate_name: d.candidate_name || '',
                              analysis: d.analysis || null,
                              session_type: d.session_type || it.session_type || 'panel',
                            }))
                            navigate('/app/workspace?mode=continue')
                          } catch (e) {
                            setError(e.message)
                          }
                        }}
                      >
                        {tr('continueInterview')}
                      </button>
                    )}
                  </td>
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
