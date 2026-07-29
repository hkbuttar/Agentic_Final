// Comparison table — renders /query's `evidence` field (already ranked and
// source-tagged "private"/"live" by the Retriever node).
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
                <td>{item.title}</td>
                <td>{item.price != null ? `$${Number(item.price).toFixed(2)}` : "—"}</td>
                <td>{item.rating ?? "—"}</td>
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
