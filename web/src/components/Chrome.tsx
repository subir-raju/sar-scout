import { useState } from "react";
import type { ReactNode } from "react";
import { liveApi } from "../lib/api";
import { AUTHOR, REPO_URL } from "../config";

const SECTIONS = [
  { id: "limits", label: "The limits" },
  { id: "try", label: "Try an event" },
  { id: "day", label: "A day of events" },
  { id: "log", label: "Audit log" },
  ...(liveApi ? [{ id: "live", label: "Live backend" }] : []),
];

/* A small radar screen: two rings, a sweep and one blip. */
export function Logo() {
  return (
    <svg className="logo-mark" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="13" className="logo-ring" />
      <circle cx="16" cy="16" r="7" className="logo-ring logo-ring--inner" />
      <path d="M16 16 L16 3 A13 13 0 0 1 27.3 9.5 Z" className="logo-sweep" />
      <circle cx="22" cy="10.5" r="2.2" className="logo-blip" />
    </svg>
  );
}

export function Header() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <header className="top">
      <div className="wrap top-in">
        <a className="brand" href="#top" onClick={close} aria-label="sar-scout, back to the top">
          <Logo />
          <span className="brand-name">sar<i>·</i>scout</span>
        </a>
        <button type="button" className="menu-btn" aria-expanded={open} aria-controls="site-nav"
          onClick={() => setOpen(!open)}>
          {open ? "Close" : "Menu"}
        </button>
        <nav id="site-nav" aria-label="Sections" className={open ? "is-open" : ""}>
          {SECTIONS.map((s) => <a key={s.id} href={`#${s.id}`} onClick={close}>{s.label}</a>)}
          <a className="nav-code" href={REPO_URL} target="_blank" rel="noreferrer">Code</a>
        </nav>
      </div>
    </header>
  );
}

/* Three dots on a radar screen, coloured like the three possible answers. */
function Radar() {
  return (
    <svg className="radar" viewBox="0 0 400 400" role="img"
      aria-label="A radar screen with three dots: teal for orders it alone, amber for asks a person, rose for says no">
      <defs>
        <linearGradient id="sweep-fill" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#1fb5a6" stopOpacity="0" />
          <stop offset="1" stopColor="#1fb5a6" stopOpacity="0.45" />
        </linearGradient>
      </defs>
      <circle cx="200" cy="200" r="190" className="radar-bg" />
      {[60, 120, 180].map((r) => <circle key={r} cx="200" cy="200" r={r} className="radar-ring" />)}
      <line x1="200" y1="10" x2="200" y2="390" className="radar-ring" />
      <line x1="10" y1="200" x2="390" y2="200" className="radar-ring" />
      <g className="radar-sweep">
        <path d="M200 200 L200 10 A190 190 0 0 1 364.5 105 Z" fill="url(#sweep-fill)" />
      </g>
      <g className="blip blip--auto"><circle cx="272" cy="118" r="9" /><text x="288" y="112">7.67</text></g>
      <g className="blip blip--ask"><circle cx="128" cy="262" r="9" /><text x="144" y="256">1.53</text></g>
      <g className="blip blip--refuse"><circle cx="292" cy="290" r="9" /><text x="308" y="284">0.41</text></g>
    </svg>
  );
}

export function Hero() {
  return (
    <section className="hero" id="top">
      <div className="wrap hero-grid">
        <div className="hero-text">
          <h1>Which satellite image should be ordered first?</h1>
          <p className="hero-lede">
            After an earthquake or a flood, many places need a radar image and only a few can have one today.
            sar-scout scores each event, then follows a written rulebook: order it alone, ask a person, or say no.
          </p>
          <ul className="legend" aria-label="The three kinds of answer">
            <li><span className="swatch swatch--auto" />Orders it alone</li>
            <li><span className="swatch swatch--ask" />Asks a person first</li>
            <li><span className="swatch swatch--refuse" />Says no</li>
          </ul>
          <div className="cta-row">
            <a className="cta cta--solid" href="#try">Try an event</a>
            <a className="cta cta--ghost" href="#day">Watch a day of events</a>
          </div>
        </div>
        <Radar />
      </div>
    </section>
  );
}

export function Section({ id, title, lede, children }: {
  id: string; title: string; lede: string; children: ReactNode;
}) {
  return (
    <section className="block" id={id} aria-labelledby={`h-${id}`}>
      <div className="wrap">
        <div className="block-head">
          <h2 id={`h-${id}`}>{title}</h2>
          <p className="lede">{lede}</p>
        </div>
        {children}
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="foot">
      <div className="wrap foot-in">
        <span className="brand brand--foot"><Logo /><span className="brand-name">sar<i>·</i>scout</span></span>
        <p>
          Built by {AUTHOR}. The events are made up and the satellite service is a mock: nothing here
          can order a real image. <a href={REPO_URL} target="_blank" rel="noreferrer">Read the code</a>.
        </p>
      </div>
    </footer>
  );
}