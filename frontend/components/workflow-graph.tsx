"use client";

import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const nodeStyle = { border: "1px solid #dbe2ea", borderRadius: 12, padding: 10, background: "#fff", color: "#0c1222", fontSize: 12, fontWeight: 600 };
const nodes: Node[] = [
  { id: "upload", position: { x: 0, y: 70 }, data: { label: "CSV datasets" }, style: nodeStyle },
  { id: "plan", position: { x: 170, y: 70 }, data: { label: "Deterministic planner" }, style: nodeStyle },
  { id: "investigate", position: { x: 360, y: 20 }, data: { label: "Investigators" }, style: nodeStyle },
  { id: "refine", position: { x: 360, y: 125 }, data: { label: "One retry gate" }, style: nodeStyle },
  { id: "report", position: { x: 570, y: 70 }, data: { label: "Impact + report" }, style: { ...nodeStyle, borderColor: "#23c7a5" } }
];
const edges: Edge[] = [
  { id: "e1", source: "upload", target: "plan", animated: true },
  { id: "e2", source: "plan", target: "investigate", animated: true },
  { id: "e3", source: "investigate", target: "refine" },
  { id: "e4", source: "refine", target: "report", animated: true },
  { id: "e5", source: "investigate", target: "report", animated: true }
];

export function WorkflowGraph() {
  return <div className="h-[240px] overflow-hidden rounded-2xl border border-slate-200 bg-slate-50"><ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.25 }} nodesDraggable={false} nodesConnectable={false}><MiniMap pannable zoomable /><Controls showInteractive={false} /><Background gap={16} size={1} /></ReactFlow></div>;
}
