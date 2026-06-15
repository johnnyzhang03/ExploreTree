// Per-vertical badge metadata: short label + accent color.
// Shared by the D3 tree (Tree.jsx) and the card view (CardView.jsx).
export const VERTICALS = {
  web: { label: "Web", color: "#1a73e8" },
  news: { label: "News", color: "#d93025" },
  finance: { label: "Finance", color: "#188038" },
  places: { label: "Places", color: "#e8710a" },
  videos: { label: "Videos", color: "#9334e6" },
};

// Verticals that actually produced sources, else the planned set; filtered to known.
export function nodeVerticals(node) {
  const fromSources = [
    ...new Set((node.sources || []).map((s) => s.vertical).filter(Boolean)),
  ];
  const list = fromSources.length ? fromSources : node.verticals || [];
  return list.filter((v) => VERTICALS[v]);
}
