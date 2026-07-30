import { Fragment, useState } from "react";
import Recorder from "./components/Recorder";
import AgentTrace from "./components/AgentTrace";
import ComparisonTable from "./components/ComparisonTable";
import AnswerPanel from "./components/AnswerPanel";
import { transcribeAudio, runQuery } from "./api";
import "./App.css";

// How many prior turns to keep sending as context for follow-ups ("the
// cheapest one", "what about under $10") — bounded so the request body
// (and the Router's prompt) doesn't grow without limit across a long
// conversation. The on-screen log itself isn't capped — it's the full
// chat history, this only bounds what's sent back to the API each turn.
const HISTORY_LIMIT = 3;

export default function App() {
  // Full conversation, oldest first: each entry is one turn's transcript +
  // its complete response (trace, evidence, answer, citations, and the
  // resolved intent — kept around only so it can be sent back as history,
  // not rendered).
  const [log, setLog] = useState([]);
  const [newText, setNewText] = useState("");
  const [followupText, setFollowupText] = useState("");
  const [status, setStatus] = useState("idle"); // idle | transcribing | querying
  const [error, setError] = useState(null);

  // `logForThisCall` is passed explicitly (rather than always reading the
  // `log` state var) so a "start new conversation" query can pass `[]` and
  // genuinely ignore prior turns, without waiting on a state reset to
  // flush first.
  async function runQueryFor(text, logForThisCall) {
    if (!text.trim()) return;
    setError(null);
    setStatus("querying");
    try {
      const history = logForThisCall.slice(-HISTORY_LIMIT).map(({ transcript, intent, evidence, answer }) => ({
        transcript,
        intent,
        evidence,
        answer,
      }));
      const queryResult = await runQuery(text, history);
      setLog([
        ...logForThisCall,
        {
          transcript: text,
          intent: queryResult.intent,
          trace: queryResult.trace,
          evidence: queryResult.evidence,
          answer: queryResult.answer,
          citations: queryResult.citations,
        },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setStatus("idle");
    }
  }

  async function handleNewAudioReady(blob) {
    setError(null);
    setStatus("transcribing");
    try {
      const { text } = await transcribeAudio(blob);
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
      await runQueryFor(text, log);
    } catch (err) {
      setError(err.message);
      setStatus("idle");
    }
  }

  function handleNewManualSubmit(event) {
    event.preventDefault();
    runQueryFor(newText, []);
    setNewText("");
  }

  function handleFollowupManualSubmit(event) {
    event.preventDefault();
    runQueryFor(followupText, log);
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

      {log.map((turn, i) => (
        <Fragment key={i}>
          <section className="panel">
            <h2>{i === 0 ? "Transcript" : "Follow-up"}</h2>
            <p>{turn.transcript}</p>
          </section>
          <AgentTrace trace={turn.trace} />
          <ComparisonTable evidence={turn.evidence} />
          <AnswerPanel answer={turn.answer} citations={turn.citations} />
        </Fragment>
      ))}

      {status === "transcribing" && <p className="status">Transcribing…</p>}
      {status === "querying" && <p className="status">Thinking…</p>}
      {error && <p className="error">{error}</p>}

      {log.length > 0 && (
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
      )}
    </div>
  );
}
