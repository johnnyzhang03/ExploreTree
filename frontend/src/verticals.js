// Per-vertical badge metadata: short label + accent color.
// Shared by the D3 tree (Tree.jsx) and the card view (CardView.jsx).
export const VERTICALS = {
  web: { label: "Web", color: "#0f6cbd" },
  news: { label: "News", color: "#c50f1f" },
  finance: { label: "Finance", color: "#107c10" },
  places: { label: "Places", color: "#ca5010" },
};

// Verticals that actually produced sources, else the planned set; filtered to known.
export function nodeVerticals(node) {
  const fromSources = [
    ...new Set((node.sources || []).map((s) => s.vertical).filter(Boolean)),
  ];
  const list = fromSources.length ? fromSources : node.verticals || [];
  return list.filter((v) => VERTICALS[v]);
}
