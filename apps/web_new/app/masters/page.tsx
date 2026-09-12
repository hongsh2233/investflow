"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import FavoriteBorder from "@mui/icons-material/FavoriteBorder";
import Favorite from "@mui/icons-material/Favorite";
import ArrowForwardIos from "@mui/icons-material/ArrowForwardIos";
import { JUBTI_MASTER_BY_TYPE, MBTI_TO_JUBTI, type JubtiDimension } from "@/lib/jubti/jubtiMasters";
import { FALLBACK_QUOTES } from "@/lib/data/masterQuotesPool";

interface Quote {
  id: number;
  name: string;
  quote: string;
  likes?: number;
  like_count?: number;
}

const MASTER_FILTERS = ["전체", "워런 버핏", "찰리 멍거", "조지 소로스", "피터 린치"];

export default function MastersPage() {
  const { data: session } = useSession();
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [current, setCurrent] = useState<Quote | null>(null);
  const [liked, setLiked] = useState(false);
  const [filter, setFilter] = useState("전체");
  const [loading, setLoading] = useState(true);

  const member = session?.user as { mbti_type?: string } | undefined;
  const mbti = member?.mbti_type || "";
  const jubtiKey = mbti ? MBTI_TO_JUBTI[mbti] : null;
  const myMaster = jubtiKey ? JUBTI_MASTER_BY_TYPE[jubtiKey as JubtiDimension] : null;

  const fetchQuotes = useCallback(async () => {
    setLoading(true);
    let loaded = false;
    try {
      const res = await fetch("/api/master-quotes?limit=50");
      if (res.ok) {
        const data = await res.json();
        const list: Quote[] = data.items || [];
        if (list.length > 0) {
          setQuotes(list);
          setCurrent(list[Math.floor(Math.random() * list.length)]);
          loaded = true;
        }
      }
    } catch {
      /* fall through to fallback */
    } finally {
      if (!loaded) {
        setQuotes(FALLBACK_QUOTES);
        setCurrent(FALLBACK_QUOTES[Math.floor(Math.random() * FALLBACK_QUOTES.length)]);
      }
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchQuotes(); }, [fetchQuotes]);

  const filteredQuotes = filter === "전체"
    ? quotes
    : quotes.filter((q) => q.name?.includes(filter.split(" ").at(-1) || ""));

  function nextQuote() {
    if (filteredQuotes.length === 0) return;
    const pool = filteredQuotes.filter((q) => q.id !== current?.id);
    const pick = pool.length > 0 ? pool : filteredQuotes;
    setCurrent(pick[Math.floor(Math.random() * pick.length)]);
    setLiked(false);
  }

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--app-bg)", padding: "0 0 6rem" }}>
      {/* 내 MBTI 매칭 배너 */}
      {myMaster && (
        <div style={{
          padding: "0.6rem 1rem",
          backgroundColor: "var(--app-bg-tertiary)",
          borderBottom: "1px solid var(--app-border)",
          fontSize: "0.82rem",
          color: "var(--app-accent)",
          display: "flex",
          alignItems: "center",
          gap: "0.4rem",
        }}>
          <span>✨</span>
          <span>
            {mbti} 성향 — 닮은 대가: <strong>{myMaster}</strong>
          </span>
        </div>
      )}

      {/* 필터 */}
      <div style={{
        display: "flex",
        gap: "0.4rem",
        padding: "0.75rem 1rem",
        overflowX: "auto",
        borderBottom: "1px solid var(--app-border)",
        scrollbarWidth: "none",
      }}>
        {MASTER_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => { setFilter(f); setLiked(false); }}
            style={{
              whiteSpace: "nowrap",
              padding: "0.35rem 0.9rem",
              borderRadius: "9999px",
              fontSize: "0.82rem",
              fontWeight: 500,
              backgroundColor: filter === f ? "var(--app-accent)" : "var(--app-card-bg)",
              color: filter === f ? "#0E0E2A" : "var(--app-text-muted)",
              border: filter === f ? "none" : "1px solid var(--app-border)",
              cursor: "pointer",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      <div style={{ padding: "1.25rem 1rem" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: "4rem", color: "var(--app-text-muted)" }}>
            명언을 불러오는 중...
          </div>
        ) : current ? (
          <>
            {/* 명언 카드 */}
            <div style={{
              backgroundColor: "var(--app-surface-elevated)",
              borderRadius: "16px",
              padding: "2rem 1.5rem",
              position: "relative",
              overflow: "hidden",
              marginBottom: "1rem",
            }}>
              {/* 인용부호 배경 */}
              <span style={{
                position: "absolute",
                top: "0.5rem",
                left: "0.75rem",
                fontSize: "5rem",
                color: "var(--app-accent)",
                opacity: 0.2,
                fontFamily: "Georgia, serif",
                lineHeight: 1,
                userSelect: "none",
              }}>"</span>

              <p style={{
                fontSize: "1.05rem",
                lineHeight: 1.8,
                color: "var(--app-text)",
                fontWeight: 400,
                marginBottom: "1.5rem",
                position: "relative",
                zIndex: 1,
              }}>
                {current.quote}
              </p>

              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}>
                <span style={{
                  fontWeight: 700,
                  color: "var(--app-accent)",
                  fontSize: "0.95rem",
                }}>
                  — {current.name}
                  {myMaster && current.name?.includes(myMaster.split(" ").at(-1) || "") && (
                    <span style={{
                      marginLeft: "0.4rem",
                      fontSize: "0.7rem",
                      backgroundColor: "var(--app-accent)",
                      color: "#0E0E2A",
                      borderRadius: "4px",
                      padding: "1px 5px",
                      fontWeight: 600,
                    }}>내 대가</span>
                  )}
                </span>
                {(current.likes ?? current.like_count) != null && (current.likes ?? current.like_count)! > 0 && (
                  <span style={{ fontSize: "0.78rem", color: "var(--app-text-muted)" }}>
                    좋아요 {(current.likes ?? current.like_count)!.toLocaleString()}
                  </span>
                )}
              </div>
            </div>

            {/* 액션 버튼 */}
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                onClick={() => setLiked((p) => !p)}
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.4rem",
                  padding: "0.75rem",
                  borderRadius: "10px",
                  backgroundColor: "var(--app-card-bg)",
                  border: `1px solid ${liked ? "var(--app-accent)" : "var(--app-border)"}`,
                  color: liked ? "var(--app-accent)" : "var(--app-text-muted)",
                  fontWeight: 600,
                  fontSize: "0.9rem",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                {liked ? <Favorite style={{ fontSize: "1.1rem" }} /> : <FavoriteBorder style={{ fontSize: "1.1rem" }} />}
                좋아요
              </button>
              <button
                onClick={nextQuote}
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.4rem",
                  padding: "0.75rem",
                  borderRadius: "10px",
                  backgroundColor: "var(--app-accent)",
                  color: "#0E0E2A",
                  fontWeight: 700,
                  fontSize: "0.9rem",
                  cursor: "pointer",
                }}
              >
                다음 명언
                <ArrowForwardIos style={{ fontSize: "0.85rem" }} />
              </button>
            </div>
          </>
        ) : (
          <div style={{ textAlign: "center", padding: "4rem", color: "var(--app-text-muted)" }}>
            {filter !== "전체" ? `${filter}의 명언이 없습니다` : "명언이 없습니다"}
          </div>
        )}
      </div>
    </div>
  );
}
