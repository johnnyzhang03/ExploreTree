import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

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
    const words = full.split(/\s+/);
    let line = [];
    let lineNum = 0;
    const y = node.attr("y");
    const x = node.attr("x");
    node.text(null);
    let tspan = node.append("tspan").attr("x", x).attr("y", y).attr("dy", "0px");
    for (const word of words) {
      line.push(word);
      tspan.text(line.join(" "));
      if (tspan.node().getComputedTextLength() > width && line.length > 1) {
        line.pop();
        tspan.text(line.join(" "));
        line = [word];
        if (lineNum >= maxLines - 1) {
          tspan.text(tspan.text() + " …");
          break;
        }
        lineNum += 1;
        tspan = node
          .append("tspan")
          .attr("x", x)
          .attr("y", y)
          .attr("dy", `${lineNum * lineHeight}px`)
          .text(word);
      }
    }
  });
}

const NODE_W = 320;
const NODE_H = 150;
const PAD = 18;

export default function Tree({ nodes }) {
  const svgRef = useRef(null);
  const gRef = useRef(null);
  const zoomRef = useRef(null);
  const posRef = useRef(new Map()); // id -> {x, y} from previous render
  const userMovedRef = useRef(false); // stop auto-fit once the user pans/zooms

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
    const linkGen = d3
      .linkVertical()
      .x((d) => d.x)
      .y((d) => d.y);

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
              return linkGen({ source: s, target: s });
            })
            .call((e) => e.transition(T()).attr("opacity", 1).attr("d", linkGen)),
        (update) =>
          update.call((u) =>
            u.interrupt().transition(T()).attr("opacity", 1).attr("d", linkGen)
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
            .attr("transform", (d) => {
              const s = startOf(d);
              return `translate(${s.x - NODE_W / 2}, ${s.y})`;
            });

          ge.append("rect")
            .attr("width", NODE_W)
            .attr("height", NODE_H)
            .attr("rx", 12);
          ge.append("text").attr("class", "node-label");
          ge.append("text").attr("class", "node-insight");

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
    node.attr("class", (d) => `node-card ${d.data.status}`);

    node
      .select("text.node-label")
      .attr("x", PAD)
      .attr("y", PAD + 14)
      .attr("data-text", (d) => d.data.label)
      .call(wrap, NODE_W - PAD * 2, 24, 2);

    node
      .select("text.node-insight")
      .attr("x", PAD)
      .attr("y", PAD + 64)
      .attr("data-text", (d) =>
        d.data.status === "searching" ? "searching…" : d.data.insight
      )
      .call(wrap, NODE_W - PAD * 2, 20, 4);

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


