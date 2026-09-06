import { Link } from 'react-router-dom'
import {
  Sparkles, Users, Target, Scale, ArrowRight, Globe, Mic, FileText, Shield
} from 'lucide-react'
import { SUPPORTED_LANGUAGES, setStoredLanguage, t } from '../i18n'

export default function Landing({ lang, setLang }) {
  const tr = (k, v) => t(k, lang, v)
  const onLang = (code) => {
    setLang(code)
    setStoredLanguage(code)
  }

  return (
    <div className="lp">
      <div className="lp-hero">
        <div className="lp-hero-bg" aria-hidden="true" />
        <div className="lp-hero-overlay" />

        <header className="lp-nav">
          <div className="lp-logo">
            <div className="brand-mark">TH</div>
            <span>{tr('appName')}</span>
          </div>
          <div className="lp-nav-right">
            <div className="lp-lang">
              <Globe size={14} />
              <select value={lang} onChange={(e) => onLang(e.target.value)} aria-label={tr('languageLabel')}>
                {SUPPORTED_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>{l.native}</option>
                ))}
              </select>
            </div>
            <Link to="/login" className="btn btn-ghost lp-btn-ghost">{tr('lpLogin')}</Link>
            <Link to="/signup" className="btn btn-primary">{tr('lpGetStarted')}</Link>
          </div>
        </header>

        <div className="lp-hero-content">
          <div className="lp-kicker">
            <Sparkles size={14} /> {tr('lpKicker')}
          </div>
          <h1 className="lp-title">
            <span className="lp-title-line">{tr('lpTitleThe')}</span>
            <span className="lp-title-main">{tr('lpTitleMain')}</span>
          </h1>
          <p className="lp-tagline">{tr('lpTagline')}</p>
          <p className="lp-lead">{tr('lpLead')}</p>
          <div className="lp-cta-row">
            <Link to="/signup" className="btn btn-primary btn-lg">
              {tr('lpEnter')} <ArrowRight size={18} />
            </Link>
            <Link to="/login" className="btn btn-outline-light btn-lg">
              {tr('lpHaveAccount')}
            </Link>
          </div>
          <div className="lp-persona-strip">
            <div className="lp-persona"><span className="dot hr" /> {tr('personaHrShort')}</div>
            <div className="lp-persona"><span className="dot tech" /> {tr('personaTechShort')}</div>
            <div className="lp-persona"><span className="dot hm" /> {tr('personaHmShort')}</div>
          </div>
        </div>
      </div>

      <section className="lp-paths">
        <h2>{tr('lpTwoWays')}</h2>
        <p className="lp-section-sub">{tr('lpTwoWaysSub')}</p>
        <div className="lp-path-grid">
          <div className="lp-path-card">
            <div className="lp-path-icon"><Mic size={22} /></div>
            <h3>{tr('lpPureTitle')}</h3>
            <p>{tr('lpPureDesc')}</p>
            <ul>
              <li>{tr('lpPure1')}</li>
              <li>{tr('lpPure2')}</li>
              <li>{tr('lpPure3')}</li>
            </ul>
          </div>
          <div className="lp-path-card accent">
            <div className="lp-path-icon"><FileText size={22} /></div>
            <h3>{tr('lpResumeTitle')}</h3>
            <p>{tr('lpResumeDesc')}</p>
            <ul>
              <li>{tr('lpResume1')}</li>
              <li>{tr('lpResume2')}</li>
              <li>{tr('lpResume3')}</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="lp-features">
        {[
          { icon: Users, title: 'lpFeatPersonas', text: 'lpFeatPersonasDesc' },
          { icon: Scale, title: 'lpFeatDelib', text: 'lpFeatDelibDesc' },
          { icon: Target, title: 'lpFeatStar', text: 'lpFeatStarDesc' },
          { icon: Shield, title: 'lpFeatData', text: 'lpFeatDataDesc' },
        ].map(({ icon: Icon, title, text }) => (
          <div className="lp-feature" key={title}>
            <div className="feature-icon"><Icon size={18} /></div>
            <h3>{tr(title)}</h3>
            <p>{tr(text)}</p>
          </div>
        ))}
      </section>

      <footer className="lp-footer">
        <div>{tr('lpFooter')}</div>
        <div className="lp-footer-lang">
          <Globe size={13} />
          <select value={lang} onChange={(e) => onLang(e.target.value)} aria-label={tr('languageLabel')}>
            {SUPPORTED_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.native}</option>
            ))}
          </select>
        </div>
      </footer>
    </div>
  )
}
