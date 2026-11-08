import { useState } from "react";
import { Footer, Header, Hero, Section } from "./components/Chrome";
import { Playground } from "./components/Playground";
import { PolicyPanel } from "./components/PolicyPanel";
import { Workflow } from "./components/Workflow";
import { Ledger } from "./components/Ledger";
import { Live } from "./components/live/Live";
import { emptyDay } from "./lib/day";
import type { Day } from "./lib/day";
import { DEFAULT_POLICY } from "./lib/scenarios";
import type { Policy } from "./lib/types";

export default function App() {
  const [policy, setPolicy] = useState<Policy>(DEFAULT_POLICY);
  const [day, setDay] = useState<Day>(emptyDay);

  return (
    <>
     <Header showLog={day.entries.length > 0} />
      <main>
        <Hero />
        <Section
          id="limits"
          title="The limits"
          lede=""
        >
          <PolicyPanel policy={policy} onChange={setPolicy} />
        </Section>
                <Section
          id="try"
          title="Try one event"
          lede=""
        >
          <Playground policy={policy} />
        </Section>
                <Section
          id="day"
          title="A day of events"
          lede=""
        >
          <Workflow policy={policy} day={day} onChange={setDay} />
        </Section>
       {day.entries.length > 0 && (
  <Section
    id="log"
    title="The audit log"
    lede="Every decision, and every answer from a person, is written to a log that cannot be quietly changed."
  >
    <Ledger entries={day.entries} />
  </Section>
)}
        <Live policy={policy} />
      </main>
      <Footer />
    </>
  );
}