"use client";

import { useState, useEffect } from "react";

interface IndexData {
  name: string;
  value: string;
  change: string;
  percent: string;
  change_num: number;
}

export function MarketIndexBar() {
  const [indices, setIndices] = useState<IndexData[]>([]);

  useEffect(() => {
    fetch("/api/domestic-indices")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d?.data?.length) setIndices(d.data); })
      .catch(() => {});
  }, []);

  return (
    <div style={{
      backgroundColor: "var(--app-card-bg)",
      borderBottom: "1px solid var(--app-border)",
      padding: "0.5rem 1rem",
      display: "flex",
      gap: "1.5rem",
      fontSize: "0.8rem",
    }}>
      {indices.length > 0 ? indices.map((idx) => {
        const isUp = (idx.change_num ?? 0) >= 0;
        const arrow = isUp ? "▲" : "▼";
        const color = isUp ? "var(--app-up)" : "var(--app-down)";
        return (
          <span key={idx.name}>
            {idx.name}{" "}
            <span style={{ color, fontFamily: "monospace" }}>
              {arrow} {idx.value} {idx.change} ({idx.percent})
            </span>
          </span>
        );
      }) : (
        <>
          <span style={{ color: "var(--app-text-muted)" }}>KOSPI —</span>
          <span style={{ color: "var(--app-text-muted)" }}>KOSDAQ —</span>
        </>
      )}
    </div>
  );
}
