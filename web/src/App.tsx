import { Footer, Header, Hero, Section } from "./components/Chrome";

export default function App() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Section id="limits" title="The limits" lede="Placeholder: the rulebook goes here.">
          <p className="empty">Coming in the next commits.</p>
        </Section>
      </main>
      <Footer />
    </>
  );
}