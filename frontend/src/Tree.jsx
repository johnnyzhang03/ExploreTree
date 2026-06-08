import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

function buildHierarchy(nodes) {
  const list = Object.values(nodes);
  const root = list.find((n) => n.parentId === null);
  if (!root) return null;
  const stratify = d3
    .stratify()
    .id((d) => d.id)
    .parentId((d) => d.parentId);
  try {
    return stratify(list);
  } catch {
    return null; // children can arrive before parent; skip until consistent
  }
}

function wrap(text, width, lineHeight, maxLines) {
  text.each(function () {
    const node = d3.select(this);
    const full = node.attr("data-text") || "";
    if (node.attr("data-wrapped") === full) return; // already wrapped this text
    node.attr("data-wrapped", full);
    const y = node.attr("y");
    const x = node.attr("x");
    node.text(null);

    // Tokenize so it works for both space-separated (latin) and CJK text:
    // keep runs of non-space as atoms, but allow breaking between CJK chars.
    const tokens = full.match(/\s+|[一-鿿　-〿＀-￯]|[^\s一-鿿　-〿＀-￯]+/g) || [];

    let lineNum = 0;
    let cur = "";
    let tspan = node.append("tspan").attr("x", x).attr("y", y).attr("dy", "0px");

    const fits = (s) => {
      tspan.text(s);
      return tspan.node().getComputedTextLength() <= width;
    };

    for (const tok of tokens) {
      const candidate = cur + tok;
      if (fits(candidate) || cur === "") {
        cur = candidate;
        continue;
      }
      // candidate overflows: commit `cur` to this line, move `tok` to the next
      tspan.text(cur.replace(/\s+$/, ""));
      if (lineNum >= maxLines - 1) {
        tspan.text(cur.replace(/\s+$/, "") + "…");
        return;
      }
      lineNum += 1;
      cur = tok.match(/^\s+$/) ? "" : tok; // don't start a line with whitespace
      tspan = node
        .append("tspan")
        .attr("x", x)
        .attr("y", y)
        .attr("dy", `${lineNum * lineHeight}px`)
        .text(cur);
    }
    tspan.text(cur.replace(/\s+$/, ""));
  });
}

const NODE_W = 320;
const NODE_H = 172;
const PAD = 18;
const HEADER_H = 64; // colored header band height

// Per-vertical badge metadata: short label + accent color.
const VERTICALS = {
  web: { label: "Web", color: "#1a73e8" },
  news: { label: "News", color: "#d93025" },
  finance: { label: "Finance", color: "#188038" },
  places: { label: "Places", color: "#e8710a" },
};

function nodeVerticals(d) {
  // prefer the verticals that actually produced sources; else the planned set
  const fromSources = [
    ...new Set((d.data.sources || []).map((s) => s.vertical).filter(Boolean)),
  ];
  const list = fromSources.length ? fromSources : d.data.verticals || [];
  return list.filter((v) => VERTICALS[v]);
}

export default function Tree({ nodes, onSelectNode, selectedId }) {
  const svgRef = useRef(null);
  const gRef = useRef(null);
  const zoomRef = useRef(null);
  const posRef = useRef(new Map()); // id -> {x, y} from previous render
  const userMovedRef = useRef(false); // stop auto-fit once the user pans/zooms
  const selectRef = useRef(onSelectNode);
  selectRef.current = onSelectNode;

  useEffect(() => {
    const root = buildHierarchy(nodes);
    const svg = d3.select(svgRef.current);
    if (!root) return;

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    if (!gRef.current) {
      gRef.current = svg.append("g");
      const zoom = d3
        .zoom()
        .scaleExtent([0.2, 1.5])
        .on("start", (e) => {
          if (e.sourceEvent) userMovedRef.current = true; // user-initiated only
        })
        .on("zoom", (e) => gRef.current.attr("transform", e.transform));
      svg.call(zoom).on("dblclick.zoom", null);
      zoomRef.current = zoom;
    }
    const g = gRef.current;

    const layout = d3.tree().nodeSize([NODE_W + 60, NODE_H + 90]);
    layout(root);

    const T = () => d3.transition().duration(450).ease(d3.easeCubicOut);
    const prev = posRef.current;
    const startOf = (d) => {
      // new nodes grow from their parent's last-known position
      const p = d.parent && prev.get(d.parent.data.id);
      return p || prev.get(d.data.id) || { x: d.x, y: d.y };
    };
    // Links run from the parent's bottom edge to the child's top edge.
    const linkGen = d3
      .linkVertical()
      .x((p) => p.x)
      .y((p) => p.y);
    const linkPath = (s, t) =>
      linkGen({
        source: { x: s.x, y: s.y + NODE_H },
        target: { x: t.x, y: t.y },
      });

    // ---- Links ----
    g.selectAll("path.link")
      .data(root.links(), (d) => d.target.data.id)
      .join(
        (enter) =>
          enter
            .append("path")
            .attr("class", "link")
            .attr("opacity", 0)
            .attr("d", (d) => {
              const s = startOf(d.target);
              return linkPath(s, s);
            })
            .call((e) =>
              e
                .transition(T())
                .attr("opacity", 1)
                .attr("d", (d) => linkPath(d.source, d.target))
            ),
        (update) =>
          update.call((u) =>
            u
              .interrupt()
              .transition(T())
              .attr("opacity", 1)
              .attr("d", (d) => linkPath(d.source, d.target))
          ),
        (exit) => exit.call((x) => x.transition(T()).attr("opacity", 0).remove())
      );

    // ---- Nodes ----
    const node = g
      .selectAll("g.node-card")
      .data(root.descendants(), (d) => d.data.id)
      .join(
        (enter) => {
          const ge = enter
            .append("g")
            .attr("class", (d) => `node-card ${d.data.status}`)
            .attr("opacity", 0)
            .style("cursor", "pointer")
            .on("click", (event, d) => {
              event.stopPropagation();
              selectRef.current && selectRef.current(d.data.id);
            })
            .attr("transform", (d) => {
              const s = startOf(d);
              return `translate(${s.x - NODE_W / 2}, ${s.y})`;
            });

          // clip content just inside the card stroke so the rounded border
          // stays fully visible (header band must not paint over it)
          ge.append("clipPath")
            .attr("id", (d) => `clip-${d.data.id}`)
            .append("rect")
            .attr("x", 1.5)
            .attr("y", 1.5)
            .attr("width", NODE_W - 3)
            .attr("height", NODE_H - 3)
            .attr("rx", 10.5);

          ge.append("rect")
            .attr("class", "card-bg")
            .attr("width", NODE_W)
            .attr("height", NODE_H)
            .attr("rx", 12);

          const content = ge
            .append("g")
            .attr("class", "node-content")
            .attr("clip-path", (d) => `url(#clip-${d.data.id})`);

          // header band (non-root) + divider line
          content
            .append("rect")
            .attr("class", "card-header")
            .attr("width", NODE_W)
            .attr("height", HEADER_H);
          content
            .append("line")
            .attr("class", "card-divider")
            .attr("x1", 0)
            .attr("x2", NODE_W)
            .attr("y1", HEADER_H)
            .attr("y2", HEADER_H);

          content.append("text").attr("class", "node-label");
          content.append("text").attr("class", "node-insight");
          content.append("g").attr("class", "node-badges");

          ge.transition(T())
            .attr("opacity", 1)
            .attr("transform", (d) => `translate(${d.x - NODE_W / 2}, ${d.y})`);
          return ge;
        },
        (update) => {
          // interrupt any in-flight enter transition so opacity never sticks below 1
          update
            .interrupt()
            .transition(T())
            .attr("opacity", 1)
            .attr("transform", (d) => `translate(${d.x - NODE_W / 2}, ${d.y})`);
          return update;
        },
        (exit) =>
          exit.call((x) => x.transition(T()).attr("opacity", 0).remove())
      );

    // status class + text refresh on every render (enter and update)
    node.attr(
      "class",
      (d) =>
        `node-card ${d.data.status}${d.data.id === selectedId ? " selected" : ""}`
    );

    const isRoot = (d) => d.data.depth === 0;

    // header band + divider hidden for the root (it's a centered title card)
    node
      .select("rect.card-header")
      .attr("display", (d) => (isRoot(d) ? "none" : null));
    node
      .select("line.card-divider")
      .attr("display", (d) => (isRoot(d) ? "none" : null));

    node
      .select("text.node-label")
      .attr("text-anchor", (d) => (isRoot(d) ? "middle" : "start"))
      .attr("x", (d) => (isRoot(d) ? NODE_W / 2 : PAD))
      .attr("y", (d) => (isRoot(d) ? NODE_H / 2 - 14 : PAD + 12))
      .attr("data-text", (d) => capitalize(d.data.label))
      .call(wrap, NODE_W - PAD * 2, 22, 2);

    node
      .select("text.node-insight")
      .attr("x", PAD)
      .attr("y", HEADER_H + PAD + 6)
      .attr("data-text", (d) =>
        isRoot(d) ? "" : d.data.status === "searching" ? "searching…" : d.data.insight
      )
      .call(wrap, NODE_W - PAD * 2, 20, 3);

    // ---- Vertical badges (bottom row) ----
    node.select("g.node-badges").each(function (d) {
      const sel = d3.select(this);
      sel.selectAll("*").remove();
      if (isRoot(d)) return;
      let x = PAD;
      const y = NODE_H - 26;
      for (const v of nodeVerticals(d)) {
        const meta = VERTICALS[v];
        const g = sel.append("g").attr("transform", `translate(${x}, ${y})`);
        const text = g
          .append("text")
          .attr("class", "badge-text")
          .attr("x", 8)
          .attr("y", 12)
          .text(meta.label);
        const w = text.node().getComputedTextLength() + 16;
        g.insert("rect", "text")
          .attr("class", "badge-bg")
          .attr("width", w)
          .attr("height", 18)
          .attr("rx", 9)
          .attr("fill", meta.color);
        x += w + 6;
      }
    });

    // remember positions for the next render's grow-from-parent
    const next = new Map();
    root.descendants().forEach((d) => next.set(d.data.id, { x: d.x, y: d.y }));
    posRef.current = next;

    // ---- Auto-fit: keep the whole tree on screen as it grows ----
    if (!userMovedRef.current && zoomRef.current) {
      const xs = root.descendants().map((d) => d.x);
      const ys = root.descendants().map((d) => d.y);
      const minX = Math.min(...xs) - NODE_W / 2;
      const maxX = Math.max(...xs) + NODE_W / 2;
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys) + NODE_H;
      const treeW = maxX - minX;
      const treeH = maxY - minY;
      const margin = 60;
      const scale = Math.min(
        1,
        (width - margin) / treeW,
        (height - margin) / treeH
      );
      const tx = width / 2 - scale * (minX + maxX) / 2;
      const ty = margin / 2 - scale * minY;
      const transform = d3.zoomIdentity.translate(tx, ty).scale(scale);
      svg.transition(T()).call(zoomRef.current.transform, transform);
    }
  }, [nodes]);

  return <svg ref={svgRef} width="100%" height="100%" />;
}


