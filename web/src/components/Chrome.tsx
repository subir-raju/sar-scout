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

export function Header() {
  return (
    <header className="top">
      <div className="wrap top-in">
        <a className="brand" href="#top">sar-scout</a>
        <nav aria-label="Sections">
          {SECTIONS.map((s) => <a key={s.id} href={`#${s.id}`}>{s.label}</a>)}
          <a href={REPO_URL} target="_blank" rel="noreferrer">Code</a>
        </nav>
      </div>
    </header>
  );
}

export function Hero() {
  return (
    <section className="hero" id="top">
      <div className="wrap">
        <h1>Which satellite image should be ordered first?</h1>
        <p className="hero-lede">
          After an earthquake or a flood, many places need a radar image and only a few can have one today.
          sar-scout scores each event, then follows a written rulebook: order it alone, ask a person, or say no.
          Every rule below runs in your browser, so you can change it and watch the answer move.
        </p>
        <ul className="legend" aria-label="The three kinds of answer">
          <li><span className="swatch swatch--auto" />Orders it alone</li>
          <li><span className="swatch swatch--ask" />Asks a person first</li>
          <li><span className="swatch swatch--refuse" />Says no</li>
        </ul>
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
        <h2 id={`h-${id}`}>{title}</h2>
        <p className="lede">{lede}</p>
        {children}
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="foot">
      <div className="wrap">
        <p>
          Built by {AUTHOR}. The events are made up and the satellite service is a mock: nothing here
          can order a real image. <a href={REPO_URL} target="_blank" rel="noreferrer">Read the code</a>.
        </p>
      </div>
    </footer>
  );
}