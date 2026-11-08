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
      <Header />
      <main>
        <Hero />
        <Section
          id="limits"
          title="The limits"
          lede="This is the rulebook, the same fields as policy.toml in the Python project. Change anything: the next two sections use whatever you set here."
        >
          <PolicyPanel policy={policy} onChange={setPolicy} />
        </Section>
                <Section
          id="try"
          title="Try one event"
          lede="Describe an event and see how it is scored, then which of the seven checks decides what happens. Move the sliders and the answer follows."
        >
          <Playground policy={policy} />
        </Section>
                <Section
          id="day"
          title="A day of events"
          lede="Nine made-up events arrive one after another. Each one goes through the same score and rulebook. When it says to ask a person, you are the person. Change a limit above and send the next event to see it bite."
        >
          <Workflow policy={policy} day={day} onChange={setDay} />
        </Section>
        <Section
          id="log"
          title="The audit log"
          lede="Every decision, and every answer from a person, is written to a log that cannot be quietly changed. Try to cheat it."
        >
          <Ledger entries={day.entries} />
        </Section>
        <Live policy={policy} />
      </main>
      <Footer />
    </>
  );
}