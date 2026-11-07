import { useState } from "react";

export default function App() {
  const [clicks, setClicks] = useState(0);
  return (
    <main className="starter">
      <h1>sar-scout</h1>
      <p>The React app is running. Edit src/App.tsx and this page updates by itself.</p>
      <button type="button" onClick={() => setClicks(clicks + 1)}>
        Clicked {clicks} times
      </button>
    </main>
  );
}