import { useState } from "react";
import { speak } from "../api";

// Answer + citations + "Play TTS" button — the button calls /speak
// separately from /query, so audio is only synthesized if the user
// actually asks to hear it (see src/api/README.md's design notes).
export default function AnswerPanel({ answer, citations }) {
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(null);

  async function handlePlay() {
    setError(null);
    setPlaying(true);
    try {
      const blob = await speak(answer);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.addEventListener("ended", () => URL.revokeObjectURL(url));
      await audio.play();
    } catch (err) {
      setError(err.message);
    } finally {
      setPlaying(false);
    }
  }

  if (!answer) return null;

  return (
    <section className="panel answer-panel">
      <h2>Answer</h2>
      <p className="answer-text">{answer}</p>
      <button type="button" className="btn btn-primary" onClick={handlePlay} disabled={playing}>
        {playing ? "Playing…" : "▶ Play"}
      </button>
      {error && <p className="error">{error}</p>}
      {citations?.length > 0 && (
        <ul className="citations">
          {citations.map((c, i) => (
            <li key={i}>
              {c.title}
              {c.url && (
                <>
                  {" — "}
                  <a href={c.url} target="_blank" rel="noreferrer">
                    source
                  </a>
                </>
              )}
              {c.doc_id && !c.url && <span className="doc-id"> (doc_id: {c.doc_id})</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
