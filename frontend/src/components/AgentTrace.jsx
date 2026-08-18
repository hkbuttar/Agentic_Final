// Agent step log — renders /query's `trace` field. Each trace line is a
// "node: detail" string (see src/agents/*.py's trace.append calls); we split
// on the first ": " to show the node as a badge, and color-code the two
// steps that carry the story: a web fallback (blue) and a safety flag (amber).
function classify(step) {
  if (/web fallback:/i.test(step)) return "step-info";
  if (/\[safety:/i.test(step)) return "step-warn";
  return "";
}

export default function AgentTrace({ trace }) {
  if (!trace?.length) return null;

  return (
    <section className="panel">
      <p className="section-label">Agent steps</p>
      <ol className="trace">
        {trace.map((step, i) => {
          const idx = step.indexOf(": ");
          const node = idx > 0 ? step.slice(0, idx) : "step";
          const detail = idx > 0 ? step.slice(idx + 2) : step;
          return (
            <li className={`step ${classify(step)}`} key={i}>
              <span className="node-badge">{node}</span>
              <span className="step-detail">{detail}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
