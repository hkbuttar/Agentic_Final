// Comparison table — renders /query's `evidence` field (already ranked and
// source-tagged "private"/"live" by the Retriever node). Title links to
// the product's real URL when one is available (private catalog rows and
// live/Shopping results both carry one; organic-fallback results always
// do). rating is genuinely absent for every private catalog row (see
// src/ingestion/README.md#known-data-quality-limitations) — not a bug,
// the source data doesn't have it. Brand: private rows have no verified
// `brand` either, but may have a `brand_inferred` heuristic guess (see
// src/ingestion/README.md's brand_inferred section) — rendered visually
// distinct (italic, "(inferred)") from a real, verified brand so the two
// are never confused.
//
// "Unit price" is `price_per_unit` rendered with its `unit` — the
// normalized price that makes differently-sized listings comparable
// (src/ingestion/clean.py derives it). Shown verbatim rather than
// filtered: it comes from a shipping weight that's unreliable for light
// items, so a handful of rows carry an implausible figure, and quietly
// dropping those would hide a known data-quality issue the README
// documents. Live/web results never have one — the search APIs don't
// return package size — so they render "—".
function formatUnitPrice(value, unit) {
  if (value == null || !unit) return "—";
  // Sub-cent per-unit prices are real for bulk/by-weight listings; $0.00
  // would read as free, so keep enough precision to stay truthful.
  const price = value >= 0.01 ? value.toFixed(2) : value.toFixed(4);
  return `$${price}/${unit}`;
}

export default function ComparisonTable({ evidence }) {
  if (!evidence?.length) return null;

  return (
    <section className="panel">
      <p className="section-label">Comparison</p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Price</th>
              <th>Unit price</th>
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
                <td>{formatUnitPrice(item.price_per_unit, item.unit)}</td>
                <td>{item.rating != null ? `${Number(item.rating).toFixed(1)} ★` : "—"}</td>
                <td>
                  {item.brand ?? (
                    item.brand_inferred ? (
                      <span className="inferred" title="Guessed from the title, not verified data">
                        {item.brand_inferred} (inferred)
                      </span>
                    ) : (
                      "—"
                    )
                  )}
                </td>
                <td>
                  {item.source === "private" ? (
                    <span className="source-pill source-catalog">Catalog</span>
                  ) : item.source === "live" ? (
                    <span className="source-pill source-live">Live web</span>
                  ) : (
                    item.source
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
