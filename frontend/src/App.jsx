import { useState } from "react";
import Recorder from "./components/Recorder";
import AgentTrace from "./components/AgentTrace";
import ComparisonTable from "./components/ComparisonTable";
import AnswerPanel from "./components/AnswerPanel";
import { transcribeAudio, runQuery } from "./api";
import "./App.css";

// How many prior turns to keep sending as context for follow-ups ("the
// cheapest one", "what about under $10") — bounded so the request body
// (and the Router's prompt) doesn't grow without limit across a long
// conversation.
const HISTORY_LIMIT = 3;

export default function App() {
  const [transcript, setTranscript] = useState("");
  const [newText, setNewText] = useState("");
  const [followupText, setFollowupText] = useState("");
  const [status, setStatus] = useState("idle"); // idle | transcribing | querying
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  // `historyForThisCall` is passed explicitly (rather than always reading
  // the `history` state var) so a "start new conversation" query can pass
  // `[]` and genuinely ignore prior turns, without waiting on a `setHistory`
  // reset to flush first.
  async function runQueryFor(text, historyForThisCall) {
    if (!text.trim()) return;
    setError(null);
    setStatus("querying");
    try {
      const queryResult = await runQuery(text, historyForThisCall);
      setResult(queryResult);
      setHistory(
        [
          ...historyForThisCall,
          {
            transcript: text,
            intent: queryResult.intent,
            evidence: queryResult.evidence,
            answer: queryResult.answer,
          },
        ].slice(-HISTORY_LIMIT)
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setStatus("idle");
    }
  }

  async function handleNewAudioReady(blob) {
    setError(null);
    setResult(null);
    setStatus("transcribing");
    try {
      const { text } = await transcribeAudio(blob);
      setTranscript(text);
      await runQueryFor(text, []);
    } catch (err) {
      setError(err.message);
      setStatus("idle");
    }
  }

  async function handleFollowupAudioReady(blob) {
    setError(null);
    setStatus("transcribing");
    try {
      const { text } = await transcribeAudio(blob);
      setTranscript(text);
      await runQueryFor(text, history);
    } catch (err) {
      setError(err.message);
      setStatus("idle");
    }
  }

  function handleNewManualSubmit(event) {
    event.preventDefault();
    setResult(null);
    setTranscript(newText);
    runQueryFor(newText, []);
    setNewText("");
  }

  function handleFollowupManualSubmit(event) {
    event.preventDefault();
    setTranscript(followupText);
    runQueryFor(followupText, history);
    setFollowupText("");
  }

  const busy = status !== "idle";

  return (
    <div className="app">
      <header>
        <h1>Product Discovery Voice Assistant</h1>
        <p className="subtitle">Ask for a product recommendation, by voice or text.</p>
      </header>

      <section className="panel input-panel">
        <Recorder onAudioReady={handleNewAudioReady} disabled={busy} />
        <form className="manual-form" onSubmit={handleNewManualSubmit}>
          <input
            type="text"
            placeholder="...or type your request"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            disabled={busy}
          />
          <button type="submit" className="btn btn-secondary" disabled={busy || !newText.trim()}>
            Send
          </button>
        </form>
      </section>

      {status === "transcribing" && <p className="status">Transcribing…</p>}
      {status === "querying" && <p className="status">Thinking…</p>}
      {error && <p className="error">{error}</p>}

      {transcript && (
        <section className="panel">
          <h2>{history.length > 1 ? "Follow-up" : "Transcript"}</h2>
          <p>{transcript}</p>
        </section>
      )}

      {result && (
        <>
          <AgentTrace trace={result.trace} />
          <ComparisonTable evidence={result.evidence} />
          <AnswerPanel answer={result.answer} citations={result.citations} />

          <section className="panel input-panel">
            <h2>Continue the conversation</h2>
            <Recorder onAudioReady={handleFollowupAudioReady} disabled={busy} />
            <form className="manual-form" onSubmit={handleFollowupManualSubmit}>
              <input
                type="text"
                placeholder='Ask a follow-up, e.g. "the cheapest one"'
                value={followupText}
                onChange={(e) => setFollowupText(e.target.value)}
                disabled={busy}
              />
              <button type="submit" className="btn btn-secondary" disabled={busy || !followupText.trim()}>
                Send
              </button>
            </form>
          </section>
        </>
      )}
    </div>
  );
}
