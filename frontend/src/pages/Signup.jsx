import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { Sparkles } from 'lucide-react'
import { t, getStoredLanguage } from '../i18n'

export default function Signup({ lang }) {
  const L = lang || getStoredLanguage()
  const tr = (k) => t(k, L)
  const { register } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 6) {
      setError(tr('passwordHint'))
      return
    }
    setLoading(true)
    try {
      await register(email.trim(), password, fullName.trim())
      navigate('/app')
    } catch (err) {
      setError(err.message || 'Could not create account')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-visual">
        <div className="auth-visual-inner">
          <div className="brand-mark lg">TH</div>
          <h2>{tr('joinTitle')}</h2>
          <p>{tr('joinSub')}</p>
          <ul className="auth-bullets">
            <li><Sparkles size={14} /> {tr('authBullet4')}</li>
            <li><Sparkles size={14} /> {tr('authBullet5')}</li>
            <li><Sparkles size={14} /> {tr('authBullet6')}</li>
          </ul>
        </div>
      </div>
      <div className="auth-form-wrap">
        <form className="auth-card" onSubmit={onSubmit}>
          <h1>{tr('createYourAccount')}</h1>
          <p className="muted">{tr('createSub')}</p>
          {error && <div className="error-box">{error}</div>}
          <label>
            {tr('fullName')}
            <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Divya Sharma" autoComplete="name" />
          </label>
          <label>
            {tr('email')}
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" />
          </label>
          <label>
            {tr('password')}
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder={tr('passwordHint')} autoComplete="new-password" />
          </label>
          <button className="btn btn-primary btn-block" disabled={loading} type="submit">
            {loading ? tr('creatingAccount') : tr('createYourAccount')}
          </button>
          <p className="auth-switch">
            {tr('alreadyHave')} <Link to="/login">{tr('loginBtn')}</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
