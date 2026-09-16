"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import FavoriteBorder from "@mui/icons-material/FavoriteBorder";
import Favorite from "@mui/icons-material/Favorite";
import ArrowForwardIos from "@mui/icons-material/ArrowForwardIos";
import AutorenewIcon from "@mui/icons-material/Autorenew";
import { JUBTI_MASTER_BY_TYPE, MBTI_TO_JUBTI, type JubtiDimension } from "@/lib/jubti/jubtiMasters";
import { FALLBACK_QUOTES } from "@/lib/data/masterQuotesPool";
import { MarketIndexBar } from "@/app/components/module/MarketIndexBar";

interface Quote {
  id: number;
  name: string;
  quote: string;
  likes?: number;
  like_count?: number;
}

const MASTER_FILTERS = ["전체", "워런 버핏", "찰리 멍거", "조지 소로스", "피터 린치"];

const MASTER_PROFILES: Record<string, { emoji: string; en: string; desc: string; style: string }> = {
  "워런 버핏": {
    emoji: "🦁",
    en: "Warren Buffett",
    desc: "가치투자의 아버지. 오마하의 현인으로 불리며, 장기 복리 투자로 세계 최고 부자 반열에 오름.",
    style: "분산 장기 보유형",
  },
  "찰리 멍거": {
    emoji: "🦉",
    en: "Charlie Munger",
    desc: "버크셔 해서웨이 부회장. 다학문적 사고와 역발상으로 버핏의 투자 철학을 완성한 파트너.",
    style: "정신 모델 활용형",
  },
  "조지 소로스": {
    emoji: "🐯",
    en: "George Soros",
    desc: "반사성 이론으로 시장 비효율을 공략. '영란은행을 무너뜨린 남자'로 알려진 거시 투자자.",
    style: "매크로 공격형",
  },
  "피터 린치": {
    emoji: "🦊",
    en: "Peter Lynch",
    desc: "마젤란 펀드를 13년간 연평균 29% 수익률로 운용. '10루타'와 일상에서 찾는 투자 철학 제창.",
    style: "성장주 발굴형",
  },
};

export default function MastersPage() {
  const { data: session } = useSession();
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [current, setCurrent] = useState<Quote | null>(null);
  const [liked, setLiked] = useState(false);
  const [filter, setFilter] = useState("전체");
  const [loading, setLoading] = useState(true);
  const [showList, setShowList] = useState(false);

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
    } catch { /* fallback */ }
    finally {
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

  const profile = current ? MASTER_PROFILES[current.name] : null;

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--app-bg)", paddingBottom: "6rem" }}>
      <MarketIndexBar />

      {/* MBTI 배너 */}
      {myMaster && (
        <div style={{
          padding: "0.6rem 1rem",
          background: "linear-gradient(90deg, var(--app-accent) 0%, #f97316 100%)",
          fontSize: "0.82rem",
          color: "#0E0E2A",
          display: "flex",
          alignItems: "center",
          gap: "0.4rem",
          fontWeight: 600,
        }}>
          <span>✨</span>
          <span>{mbti} 성향 — 나의 닮은 대가: <strong>{myMaster}</strong></span>
        </div>
      )}

      {/* 필터 탭 */}
      <div style={{
        display: "flex",
        gap: "0.4rem",
        padding: "0.75rem 1rem",
        overflowX: "auto",
        borderBottom: "1px solid var(--app-border)",
        scrollbarWidth: "none",
        backgroundColor: "var(--app-card-bg)",
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
              backgroundColor: filter === f ? "var(--app-accent)" : "transparent",
              color: filter === f ? "#0E0E2A" : "var(--app-text-muted)",
              border: filter === f ? "none" : "1px solid var(--app-border)",
              cursor: "pointer",
            }}
          >{f}</button>
        ))}
      </div>

      {/* 메인 콘텐츠 */}
      <div style={{ maxWidth: "960px", margin: "0 auto", padding: "1.25rem 1rem" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: "4rem", color: "var(--app-text-muted)" }}>
            명언을 불러오는 중...
          </div>
        ) : current ? (
          <>
            {/* 대가 프로필 */}
            {profile && (
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                marginBottom: "0.75rem",
                padding: "0.75rem 1rem",
                backgroundColor: "var(--app-card-bg)",
                borderRadius: "12px",
                border: "1px solid var(--app-border)",
              }}>
                <span style={{ fontSize: "2rem" }}>{profile.emoji}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--app-text)" }}>
                    {current.name}
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
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--app-text-muted)" }}>{profile.en} · {profile.style}</div>
                </div>
                <span style={{
                  fontSize: "0.72rem",
                  padding: "0.2rem 0.55rem",
                  border: "1px solid var(--app-border)",
                  borderRadius: "9999px",
                  color: "var(--app-text-muted)",
                  whiteSpace: "nowrap",
                }}>
                  명언 {filteredQuotes.filter(q => q.name === current.name).length}개
                </span>
              </div>
            )}

            {/* 명언 카드 */}
            <div style={{
              backgroundColor: "var(--app-card-bg)",
              borderRadius: "16px",
              padding: "2rem 1.5rem 1.5rem",
              position: "relative",
              overflow: "hidden",
              marginBottom: "0.75rem",
              border: "1px solid var(--app-border)",
              boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
            }}>
              <span style={{
                position: "absolute",
                top: "0.25rem",
                left: "0.75rem",
                fontSize: "5rem",
                color: "var(--app-accent)",
                opacity: 0.15,
                fontFamily: "Georgia, serif",
                lineHeight: 1,
                userSelect: "none",
              }}>"</span>

              <p style={{
                fontSize: "1.08rem",
                lineHeight: 1.85,
                color: "var(--app-text)",
                fontWeight: 500,
                marginBottom: "1.25rem",
                position: "relative",
                zIndex: 1,
                paddingTop: "0.5rem",
              }}>
                {current.quote}
              </p>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 700, color: "var(--app-accent)", fontSize: "0.9rem" }}>
                  — {current.name}
                </span>
                {(current.likes ?? current.like_count ?? 0) > 0 && (
                  <span style={{ fontSize: "0.75rem", color: "var(--app-text-muted)" }}>
                    ♥ {(current.likes ?? current.like_count)!.toLocaleString()}
                  </span>
                )}
              </div>
            </div>

            {/* 대가 소개 */}
            {profile && (
              <div style={{
                padding: "0.85rem 1rem",
                backgroundColor: "var(--app-bg)",
                borderRadius: "10px",
                border: "1px solid var(--app-border)",
                marginBottom: "0.75rem",
                fontSize: "0.82rem",
                color: "var(--app-text-muted)",
                lineHeight: 1.7,
              }}>
                💡 {profile.desc}
              </div>
            )}

            {/* 액션 버튼 */}
            <div style={{ display: "flex", gap: "0.6rem", marginBottom: "1.5rem" }}>
              <button
                onClick={() => setLiked((p) => !p)}
                style={{
                  flex: 1,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem",
                  padding: "0.75rem",
                  borderRadius: "10px",
                  backgroundColor: liked ? "rgba(249,115,22,0.08)" : "var(--app-card-bg)",
                  border: `1px solid ${liked ? "var(--app-accent)" : "var(--app-border)"}`,
                  color: liked ? "var(--app-accent)" : "var(--app-text-muted)",
                  fontWeight: 600, fontSize: "0.9rem", cursor: "pointer", transition: "all 0.2s",
                }}
              >
                {liked ? <Favorite style={{ fontSize: "1.1rem" }} /> : <FavoriteBorder style={{ fontSize: "1.1rem" }} />}
                좋아요
              </button>
              <button
                onClick={nextQuote}
                style={{
                  flex: 2,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem",
                  padding: "0.75rem",
                  borderRadius: "10px",
                  backgroundColor: "var(--app-accent)",
                  color: "#0E0E2A",
                  fontWeight: 700, fontSize: "0.9rem", cursor: "pointer", border: "none",
                }}
              >
                <AutorenewIcon style={{ fontSize: "1.1rem" }} />
                다음 명언
                <ArrowForwardIos style={{ fontSize: "0.85rem" }} />
              </button>
            </div>

            {/* 명언 목록 토글 */}
            <div style={{ marginBottom: "1rem" }}>
              <button
                onClick={() => setShowList((p) => !p)}
                style={{
                  width: "100%",
                  padding: "0.65rem",
                  borderRadius: "10px",
                  backgroundColor: "var(--app-card-bg)",
                  border: "1px solid var(--app-border)",
                  color: "var(--app-text-muted)",
                  fontWeight: 600,
                  fontSize: "0.85rem",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.4rem",
                }}
              >
                📖 전체 명언 보기 ({filteredQuotes.length}개) {showList ? "▲" : "▼"}
              </button>
            </div>

            {/* 명언 목록 */}
            {showList && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                {filteredQuotes.map((q) => (
                  <div
                    key={q.id}
                    onClick={() => { setCurrent(q); setLiked(false); setShowList(false); window.scrollTo({ top: 0, behavior: "smooth" }); }}
                    style={{
                      padding: "0.9rem 1rem",
                      backgroundColor: current.id === q.id ? "rgba(249,115,22,0.08)" : "var(--app-card-bg)",
                      borderRadius: "10px",
                      border: `1px solid ${current.id === q.id ? "var(--app-accent)" : "var(--app-border)"}`,
                      cursor: "pointer",
                      transition: "all 0.15s",
                    }}
                  >
                    <p style={{
                      fontSize: "0.85rem",
                      color: "var(--app-text)",
                      lineHeight: 1.65,
                      margin: "0 0 0.4rem",
                      fontWeight: current.id === q.id ? 600 : 400,
                    }}>
                      {q.quote}
                    </p>
                    <span style={{ fontSize: "0.75rem", color: "var(--app-accent)", fontWeight: 600 }}>
                      — {q.name}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* 대가 프로필 카드 4개 */}
            <div style={{ marginTop: "1.5rem" }}>
              <h3 style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--app-text-muted)", marginBottom: "0.75rem" }}>
                투자 대가 소개
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                {Object.entries(MASTER_PROFILES).map(([name, info]) => (
                  <div
                    key={name}
                    onClick={() => { setFilter(name); setShowList(false); }}
                    style={{
                      padding: "0.85rem",
                      backgroundColor: filter === name ? "rgba(249,115,22,0.08)" : "var(--app-card-bg)",
                      borderRadius: "12px",
                      border: `1px solid ${filter === name ? "var(--app-accent)" : "var(--app-border)"}`,
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ fontSize: "1.5rem", marginBottom: "0.4rem" }}>{info.emoji}</div>
                    <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--app-text)", marginBottom: "0.2rem" }}>{name}</div>
                    <div style={{ fontSize: "0.72rem", color: "var(--app-text-muted)" }}>{info.style}</div>
                  </div>
                ))}
              </div>
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
