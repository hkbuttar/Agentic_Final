import { useState } from "react";
import Recorder from "./components/Recorder";
import AgentTrace from "./components/AgentTrace";
import ComparisonTable from "./components/ComparisonTable";
import AnswerPanel from "./components/AnswerPanel";
import { transcribeAudio, runQuery } from "./api";
import "./App.css";

export default function App() {
  const [transcript, setTranscript] = useState("");
  const [manualText, setManualText] = useState("");
  const [status, setStatus] = useState("idle"); // idle | transcribing | querying
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function runQueryFor(text) {
    if (!text.trim()) return;
    setError(null);
    setStatus("querying");
    try {
      setResult(await runQuery(text));
    } catch (err) {
      setError(err.message);
    } finally {
      setStatus("idle");
    }
  }

  async function handleAudioReady(blob) {
    setError(null);
    setResult(null);
    setStatus("transcribing");
    try {
      const { text } = await transcribeAudio(blob);
      setTranscript(text);
      await runQueryFor(text);
    } catch (err) {
      setError(err.message);
      setStatus("idle");
    }
  }

  function handleManualSubmit(event) {
    event.preventDefault();
    setResult(null);
    setTranscript(manualText);
    runQueryFor(manualText);
  }

  const busy = status !== "idle";

  return (
    <div className="app">
      <header>
        <h1>Product Discovery Voice Assistant</h1>
        <p className="subtitle">Ask for a product recommendation, by voice or text.</p>
      </header>

      <section className="panel input-panel">
        <Recorder onAudioReady={handleAudioReady} disabled={busy} />
        <form className="manual-form" onSubmit={handleManualSubmit}>
          <input
            type="text"
            placeholder="...or type your request"
            value={manualText}
            onChange={(e) => setManualText(e.target.value)}
            disabled={busy}
          />
          <button type="submit" className="btn btn-secondary" disabled={busy || !manualText.trim()}>
            Send
          </button>
        </form>
      </section>

      {status === "transcribing" && <p className="status">Transcribing…</p>}
      {status === "querying" && <p className="status">Thinking…</p>}
      {error && <p className="error">{error}</p>}

      {transcript && (
        <section className="panel">
          <h2>Transcript</h2>
          <p>{transcript}</p>
        </section>
      )}

      {result && (
        <>
          <AgentTrace trace={result.trace} />
          <ComparisonTable evidence={result.evidence} />
          <AnswerPanel answer={result.answer} citations={result.citations} />
        </>
      )}
    </div>
  );
}
