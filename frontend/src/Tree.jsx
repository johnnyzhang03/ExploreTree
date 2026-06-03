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

function wrap(text, width) {
  text.each(function () {
    const node = d3.select(this);
    const words = (node.text() || "").split(/\s+/);
    let line = [];
    let lineNum = 0;
    const lineHeight = 14;
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
        if (lineNum >= 2) {
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

const NODE_W = 200;
const NODE_H = 90;

export default function Tree({ nodes }) {
  const svgRef = useRef(null);

  useEffect(() => {
    const root = buildHierarchy(nodes);
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    if (!root) return;

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const layout = d3.tree().nodeSize([NODE_W + 40, NODE_H + 70]);
    layout(root);

    const xs = root.descendants().map((d) => d.x);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const offsetX = width / 2 - (minX + maxX) / 2;
    const g = svg.append("g").attr("transform", `translate(${offsetX}, 60)`);

    g.selectAll("path.link")
      .data(root.links())
      .join("path")
      .attr("class", "link")
      .attr(
        "d",
        d3
          .linkVertical()
          .x((d) => d.x)
          .y((d) => d.y)
      );

    const node = g
      .selectAll("g.node-card")
      .data(root.descendants(), (d) => d.id)
      .join("g")
      .attr("class", (d) => `node-card ${d.data.status}`)
      .attr("transform", (d) => `translate(${d.x - NODE_W / 2}, ${d.y})`);

    node
      .append("rect")
      .attr("width", NODE_W)
      .attr("height", NODE_H)
      .attr("rx", 8);

    node
      .append("text")
      .attr("class", "node-label")
      .attr("x", 12)
      .attr("y", 22)
      .text((d) => d.data.label)
      .call(wrap, NODE_W - 24);

    node
      .append("text")
      .attr("class", "node-insight")
      .attr("x", 12)
      .attr("y", 58)
      .text((d) =>
        d.data.status === "searching" ? "searching…" : d.data.insight
      )
      .call(wrap, NODE_W - 24);
  }, [nodes]);

  return <svg ref={svgRef} width="100%" height="100%" />;
}
