"use client";

/**
 * Spatial mission topology renderer — Sprint 7.
 *
 * SVG-based, no third-party graph library. We compute a deterministic
 * cluster-aware layout in pure JS so the cockpit can render the topology
 * without runtime physics or animation churn.
 *
 * Doctrine: the graph is *strategic*, not exhaustive. Edges are restrained,
 * propagation paths animate with a calm dashed pulse only when they end in
 * critical/strain missions. Reduced-motion users see a still graph.
 */

import { useMemo } from "react";
import type {
  PropagationPath,
  TopologyEdge,
  TopologyNode,
  TopologyView,
} from "@/types/api";

type Pos = { x: number; y: number };

const PADDING = 56;
const NODE_RADIUS = 16;
const KIND_ORDER: Record<string, number> = {
  intel_item: 0,
  investor_firm: 1,
  account: 2,
  supplier: 3,
  program: 4,
  mission: 5,
  agent: 6,
};

const BAND_COLOR: Record<string, string> = {
  nominal: "#3fd29a",
  watch: "#f0b429",
  strain: "#f97316",
  critical: "#ff5a6b",
  calm: "#3fd29a",
  active: "#22d3ee",
  elevated: "#f0b429",
};

const KIND_COLOR: Record<string, string> = {
  mission: "#22d3ee",
  supplier: "#8d99ac",
  program: "#4d9eff",
  investor_firm: "#2dd4bf",
  account: "#a78bfa",
  intel_item: "#f0b429",
  agent: "#3fd29a",
};

function clusterKey(n: TopologyNode): string {
  return n.cluster ?? n.kind;
}

function layoutNodes(
  nodes: TopologyNode[],
  width: number,
  height: number,
): Map<string, Pos> {
  const positions = new Map<string, Pos>();
  if (nodes.length === 0) return positions;

  // Group by cluster.
  const clusters = new Map<string, TopologyNode[]>();
  for (const n of nodes) {
    const k = clusterKey(n);
    if (!clusters.has(k)) clusters.set(k, []);
    clusters.get(k)!.push(n);
  }
  // Order clusters: missions first (centered), other kinds around them.
  const orderedClusters = Array.from(clusters.entries()).sort(([a], [b]) => {
    const aMission = a.startsWith("mission") ? 0 : 1;
    const bMission = b.startsWith("mission") ? 0 : 1;
    return aMission - bMission || a.localeCompare(b);
  });

  const innerW = Math.max(1, width - PADDING * 2);
  const innerH = Math.max(1, height - PADDING * 2);
  const cols = Math.ceil(Math.sqrt(orderedClusters.length));
  const rows = Math.ceil(orderedClusters.length / cols);
  const cellW = innerW / cols;
  const cellH = innerH / rows;

  orderedClusters.forEach(([, group], idx) => {
    const r = Math.floor(idx / cols);
    const c = idx % cols;
    const cx = PADDING + cellW * c + cellW / 2;
    const cy = PADDING + cellH * r + cellH / 2;
    const radius = Math.min(cellW, cellH) * 0.34;
    const sorted = [...group].sort(
      (a, b) =>
        (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9) ||
        a.label.localeCompare(b.label),
    );
    sorted.forEach((n, i) => {
      const angle = (i / Math.max(1, sorted.length)) * Math.PI * 2;
      const x = cx + Math.cos(angle) * radius;
      const y = cy + Math.sin(angle) * radius;
      positions.set(n.id, { x, y });
    });
  });

  return positions;
}

function edgePath(a: Pos, b: Pos): string {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  // small lateral offset for a calm curve
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.max(1, Math.hypot(dx, dy));
  const nx = -dy / len;
  const ny = dx / len;
  const cx = mx + nx * 12;
  const cy = my + ny * 12;
  return `M${a.x},${a.y} Q${cx},${cy} ${b.x},${b.y}`;
}

export function TopologyGraph({
  view,
  width = 960,
  height = 560,
  highlightedPath,
}: {
  view: TopologyView;
  width?: number;
  height?: number;
  highlightedPath?: PropagationPath | null;
}) {
  const positions = useMemo(
    () => layoutNodes(view.nodes, width, height),
    [view.nodes, width, height],
  );

  const highlightSet = useMemo(() => {
    if (!highlightedPath) return new Set<string>();
    return new Set(highlightedPath.path);
  }, [highlightedPath]);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-auto w-full select-none"
      role="img"
      aria-label="Mission topology"
    >
      <defs>
        <radialGradient id="topology-bg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(34,211,238,0.04)" />
          <stop offset="100%" stopColor="rgba(2,4,7,0)" />
        </radialGradient>
        <marker
          id="topology-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto"
        >
          <path d="M0,0 L10,5 L0,10 z" fill="currentColor" opacity="0.6" />
        </marker>
      </defs>

      <rect width={width} height={height} fill="url(#topology-bg)" />

      {/* edges */}
      {view.edges.map((e: TopologyEdge) => {
        const a = positions.get(e.source);
        const b = positions.get(e.target);
        if (!a || !b) return null;
        const isHighlighted =
          highlightSet.has(e.source) && highlightSet.has(e.target);
        const intensity = Math.max(8, Math.min(100, e.intensity)) / 100;
        const stroke =
          e.propagation === "downstream"
            ? "#f0b429"
            : e.propagation === "upstream"
            ? "#22d3ee"
            : "#5a6677";
        const opacity = 0.25 + intensity * 0.5;
        return (
          <g
            key={e.id}
            className={isHighlighted ? "" : "animate-topology-breathe"}
          >
            <path
              d={edgePath(a, b)}
              stroke={stroke}
              strokeOpacity={isHighlighted ? 1 : opacity}
              strokeWidth={isHighlighted ? 2.4 : 1.2 + intensity * 1.4}
              fill="none"
              markerEnd="url(#topology-arrow)"
              className={
                isHighlighted ? "animate-propagation-pulse" : undefined
              }
              strokeDasharray={isHighlighted ? "8 4" : undefined}
              style={{ color: stroke }}
            />
          </g>
        );
      })}

      {/* nodes */}
      {view.nodes.map((n) => {
        const p = positions.get(n.id);
        if (!p) return null;
        const fill = BAND_COLOR[n.band] ?? KIND_COLOR[n.kind] ?? "#5a6677";
        const stroke = KIND_COLOR[n.kind] ?? "#22d3ee";
        const isHighlighted = highlightSet.has(n.id);
        const r = NODE_RADIUS * (n.kind === "mission" ? 1 : 0.78);
        return (
          <g key={n.id}>
            <circle
              cx={p.x}
              cy={p.y}
              r={r + 6}
              fill={fill}
              opacity={isHighlighted ? 0.18 : 0.08}
            />
            <circle
              cx={p.x}
              cy={p.y}
              r={r}
              fill="#0a0f17"
              stroke={stroke}
              strokeWidth={isHighlighted ? 2.5 : 1.4}
              opacity={0.95}
            />
            <text
              x={p.x}
              y={p.y + 3}
              textAnchor="middle"
              fontSize={9}
              fill="#d8dfec"
              fontFamily="ui-monospace, monospace"
            >
              {n.kind === "mission"
                ? n.label.slice(0, 6)
                : n.label.slice(0, 3).toUpperCase()}
            </text>
            <text
              x={p.x}
              y={p.y + r + 12}
              textAnchor="middle"
              fontSize={9}
              fill="#8d99ac"
              fontFamily="ui-monospace, monospace"
            >
              {n.label.length > 18 ? `${n.label.slice(0, 16)}…` : n.label}
            </text>
            {n.band !== "nominal" && (
              <circle
                cx={p.x + r - 2}
                cy={p.y - r + 2}
                r={3}
                fill={BAND_COLOR[n.band] ?? "#22d3ee"}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}
