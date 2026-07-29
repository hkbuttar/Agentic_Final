// Agent step log — renders /query's `trace` field directly.
export default function AgentTrace({ trace }) {
  if (!trace?.length) return null;

  return (
    <section className="panel">
      <h2>Agent Step Log</h2>
      <ol className="trace">
        {trace.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
    </section>
  );
}
