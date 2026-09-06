import { useState } from 'react'
import { useAuth } from '../AuthContext'
import { t, getStoredLanguage } from '../i18n'

export default function Profile({ lang }) {
  const L = lang || getStoredLanguage()
  const tr = (k) => t(k, L)
  const { user, updateProfile } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [targetRole, setTargetRole] = useState(user?.target_role || 'sde')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function save(e) {
    e.preventDefault()
    setError('')
    setMsg('')
    setLoading(true)
    try {
      await updateProfile({ full_name: fullName, target_role: targetRole })
      setMsg(tr('profileUpdated'))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dash">
      <div className="page-header">
        <div>
          <h1>{tr('profileTitle')}</h1>
          <p className="muted">{tr('profileSub')}</p>
        </div>
      </div>
      <form className="card form-card" onSubmit={save}>
        {error && <div className="error-box">{error}</div>}
        {msg && <div className="success-box">{msg}</div>}
        <label>
          {tr('email')}
          <input type="email" value={user?.email || ''} disabled />
        </label>
        <label>
          {tr('fullName')}
          <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </label>
        <label>
          {tr('targetRoleLabel')}
          <select value={targetRole} onChange={(e) => setTargetRole(e.target.value)}>
            <option value="sde">{tr('roleSde')}</option>
            <option value="data">{tr('roleData')}</option>
            <option value="product">{tr('roleProduct')}</option>
            <option value="internship">{tr('roleInternship')}</option>
          </select>
        </label>
        <button className="btn btn-primary" disabled={loading} type="submit">
          {loading ? tr('saving') : tr('saveChanges')}
        </button>
      </form>
    </div>
  )
}
