import { useAuth } from '../AuthContext'
import { SUPPORTED_LANGUAGES, setStoredLanguage, t } from '../i18n'
import { useNavigate } from 'react-router-dom'

export default function Settings({ lang, setLang }) {
  const { user, updateProfile, logout } = useAuth()
  const navigate = useNavigate()
  const tr = (k, v) => t(k, lang, v)

  async function onLang(code) {
    setLang(code)
    setStoredLanguage(code)
    try {
      await updateProfile({ preferred_language: code })
    } catch {}
  }

  return (
    <div className="dash">
      <div className="page-header">
        <div>
          <h1>{tr('settingsTitle')}</h1>
          <p className="muted">{tr('settingsSub')}</p>
        </div>
      </div>
      <div className="card form-card">
        <label>
          {tr('languageLabel')}
          <select value={lang} onChange={(e) => onLang(e.target.value)}>
            {SUPPORTED_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.native} ({l.label})</option>
            ))}
          </select>
        </label>
        <p className="muted" style={{ fontSize: '0.85rem' }}>
          {tr('languageHint', { email: user?.email || '' })}
        </p>
        <hr className="soft-hr" />
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => { logout(); navigate('/login') }}
        >
          {tr('logout')}
        </button>
      </div>
    </div>
  )
}
