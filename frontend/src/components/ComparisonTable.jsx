// Comparison table — renders /query's `evidence` field (already ranked and
// source-tagged "private"/"live" by the Retriever node). Title links to
// the product's real URL when one is available (private catalog rows and
// live/Shopping results both carry one; organic-fallback results always
// do). rating/brand are genuinely absent for every private catalog row
// (see src/ingestion/README.md#known-data-quality-limitations) — that's
// not a bug, the source data doesn't have them.
export default function ComparisonTable({ evidence }) {
  if (!evidence?.length) return null;

  return (
    <section className="panel">
      <h2>Comparison</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Price</th>
              <th>Rating</th>
              <th>Brand</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {evidence.map((item) => (
              <tr key={item.doc_id ?? item.url}>
                <td>
                  {item.url ? (
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                  ) : (
                    item.title
                  )}
                </td>
                <td>{item.price != null ? `$${Number(item.price).toFixed(2)}` : "—"}</td>
                <td>{item.rating != null ? `${Number(item.rating).toFixed(1)} ★` : "—"}</td>
                <td>{item.brand ?? "—"}</td>
                <td>{item.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
