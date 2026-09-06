import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import {
  LayoutDashboard, FileText, Mic, BarChart3, History, User, Settings,
  LogOut, Menu, X, Sparkles, Globe
} from 'lucide-react'
import { useAuth } from './AuthContext'
import { SUPPORTED_LANGUAGES, setStoredLanguage, t } from './i18n'

const NAV = [
  { to: '/app', end: true, icon: LayoutDashboard, labelKey: 'navDashboard' },
  { to: '/app/resume', icon: FileText, labelKey: 'navResume' },
  { to: '/app/interviews', icon: Mic, labelKey: 'navInterviews' },
  { to: '/app/performance', icon: BarChart3, labelKey: 'navPerformance' },
  { to: '/app/history', icon: History, labelKey: 'navHistory' },
  { to: '/app/profile', icon: User, labelKey: 'navProfile' },
  { to: '/app/settings', icon: Settings, labelKey: 'navSettings' },
]

export default function Layout({ lang, setLang }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const tr = (k, vars) => t(k, lang || 'en', vars)

  const onLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">TH</div>
          <div>
            <div className="brand-title">{tr('appName')}</div>
            <div className="brand-sub">{tr('tagline')}</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {NAV.map(({ to, end, icon: Icon, labelKey }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              onClick={() => setOpen(false)}
            >
              <Icon size={18} />
              <span>{tr(labelKey)}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="user-chip">
            <div className="user-avatar">
              {(user?.full_name || user?.email || '?')[0]?.toUpperCase()}
            </div>
            <div className="user-meta">
              <div className="user-name">{user?.full_name || 'User'}</div>
              <div className="user-email">{user?.email}</div>
            </div>
          </div>
          <button type="button" className="btn btn-ghost btn-block" onClick={onLogout}>
            <LogOut size={16} /> {tr('logout')}
          </button>
        </div>
      </aside>
      {open && <div className="sidebar-backdrop" onClick={() => setOpen(false)} />}
      <div className="main-col">
        <header className="topbar-app">
          <button type="button" className="btn btn-ghost menu-btn" onClick={() => setOpen((v) => !v)}>
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
          <div className="topbar-spacer" />
          <div className="lang-wrap">
            <Globe size={14} />
            <select
              value={lang || 'en'}
              onChange={(e) => {
                setLang(e.target.value)
                setStoredLanguage(e.target.value)
              }}
              aria-label={tr('languageLabel')}
            >
              {SUPPORTED_LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>{l.native}</option>
              ))}
            </select>
          </div>
          <div className="pill accent"><Sparkles size={12} /> {tr('aiPanel')}</div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
