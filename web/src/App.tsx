import { useState } from "react";
import { Footer, Header, Hero, Section } from "./components/Chrome";
import { PolicyPanel } from "./components/PolicyPanel";
import { DEFAULT_POLICY } from "./lib/scenarios";
import type { Policy } from "./lib/types";

export default function App() {
  const [policy, setPolicy] = useState<Policy>(DEFAULT_POLICY);

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
      </main>
      <Footer />
    </>
  );
}