"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { ZODIAC_ANIMAL_EMOJI, ZODIAC_SIGN_EMOJI } from "@/lib/utils/zodiacUtils";
import { getLocalFortune } from "@/lib/data/fortunePool";

type FortuneType = "animal" | "zodiac" | "mbti";

interface FortuneData {
  fortune_text?: string;
  investment_tip?: string;
  stars?: number;
  score?: number;
  fortune?: string;
  tip?: string;
}

interface NewsItem {
  title: string;
  link: string;
  pubDate: string;
}

const MBTI_INVEST_STYLE: Record<string, string> = {
  INTJ: "장기 전략형", INTP: "논리 분석형", ENTJ: "지휘관형", ENTP: "역발상형",
  ISTJ: "안정 장기형", ISFJ: "분산 투자형", ESTJ: "체계 관리형", ESFJ: "관계 기반형",
  ISTP: "단기 기회형", ESTP: "고수익 트레이더형", ENFJ: "테마 섹터형", ENFP: "트렌드 포착형",
  INFJ: "가치투자형", INFP: "철학적 투자형", ESFP: "즉흥 투자형", ISFP: "직관 타이밍형",
};

const MBTI_MASTER: Record<string, string> = {
  INTJ: "찰리 멍거", INTP: "찰리 멍거", ENTJ: "찰리 멍거", ENTP: "찰리 멍거",
  ISTJ: "워런 버핏", ISFJ: "워런 버핏", ESTJ: "워런 버핏", ESFJ: "워런 버핏",
  ISTP: "조지 소로스", ESTP: "조지 소로스", ENFJ: "조지 소로스", ENFP: "조지 소로스",
  INFJ: "피터 린치", INFP: "피터 린치", ESFP: "피터 린치", ISFP: "피터 린치",
};

const TODAY = new Date().toLocaleDateString("ko-KR", {
  year: "numeric", month: "long", day: "numeric", weekday: "long",
});

const ANIMALS = ["쥐","소","호랑이","토끼","용","뱀","말","양","원숭이","닭","개","돼지"];
const SIGNS = ["양자리","황소자리","쌍둥이자리","게자리","사자자리","처녀자리","천칭자리","전갈자리","사수자리","염소자리","물병자리","물고기자리"];

export default function FortunePage() {
  const { data: session } = useSession();
  const [activeTab, setActiveTab] = useState<FortuneType>("animal");
  const [selectedAnimal, setSelectedAnimal] = useState<string>("");
  const [selectedSign, setSelectedSign] = useState<string>("");
  const [fortune, setFortune] = useState<FortuneData | null>(null);
  const [loading, setLoading] = useState(false);
  const [news, setNews] = useState<NewsItem[]>([]);

  const member = session?.user as { zodiac_animal?: string; zodiac_sign?: string; mbti_type?: string } | undefined;
  const animal = member?.zodiac_animal || selectedAnimal;
  const sign = member?.zodiac_sign || selectedSign;
  const mbti = member?.mbti_type || "";

  const fetchFortune = useCallback(async (type: "animal" | "zodiac", key: string) => {
    if (!key) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/fortune/today?fortune_type=${type}&key=${encodeURIComponent(key)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success !== false && (data.fortune_text || data.fortune)) {
          setFortune(data);
          setLoading(false);
          return;
        }
      }
    } catch { /* fall through to local fallback */ }
    const local = getLocalFortune(type, key);
    if (local) {
      setFortune({ fortune_text: local.fortune, investment_tip: local.investment_tip });
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (activeTab === "animal" && animal) fetchFortune("animal", animal);
    if (activeTab === "zodiac" && sign) fetchFortune("zodiac", sign);
  }, [activeTab, animal, sign, fetchFortune]);

  useEffect(() => {
    fetch("/api/naver-news?query=주식&display=3&sort=date")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d?.data?.length) setNews(d.data.slice(0, 3)); })
      .catch(() => {});
  }, []);

  function handleAnimalSelect(a: string) {
    setSelectedAnimal(a);
    setFortune(null);
    fetchFortune("animal", a);
  }

  function handleSignSelect(s: string) {
    setSelectedSign(s);
    setFortune(null);
    fetchFortune("zodiac", s);
  }

  const fortuneText = fortune?.fortune_text || fortune?.fortune;
  const investTip = fortune?.investment_tip || fortune?.tip;
  const stars = fortune?.stars ?? fortune?.score ?? 0;

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--app-bg)", padding: "0 0 6rem" }}>
      {/* 운세 헤더 배너 */}
      <div style={{
        background: "linear-gradient(135deg, #1A1A3E 0%, #2D2D6B 100%)",
        padding: "1.25rem 1rem 1rem",
        position: "relative",
        overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", top: "-20px", right: "-10px",
          fontSize: "5rem", opacity: 0.08, pointerEvents: "none", userSelect: "none",
        }}>✨</div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.25rem" }}>
          <span style={{ fontSize: "1.4rem" }}>🔮</span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#F59E0B" }}>오늘의 투자 운세</span>
        </div>
        <p style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.6)", margin: 0 }}>{TODAY}</p>
      </div>

      {/* 지수 한 줄 */}
      <div style={{
        backgroundColor: "var(--app-card-bg)",
        borderBottom: "1px solid var(--app-border)",
        padding: "0.5rem 1rem",
        display: "flex",
        gap: "1.5rem",
        fontSize: "0.8rem",
      }}>
        <span>KOSPI <span style={{ color: "var(--app-up)", fontFamily: "monospace" }}>▲ 2,620.15 +1.23%</span></span>
        <span>KOSDAQ <span style={{ color: "var(--app-up)", fontFamily: "monospace" }}>▲ 781.40 +0.87%</span></span>
      </div>

      <div style={{ padding: "1rem" }}>
        {/* 유형 탭 */}
        <div style={{
          display: "flex", gap: "0.5rem", marginBottom: "1.5rem",
          borderBottom: "1px solid var(--app-border)", paddingBottom: "0.75rem",
        }}>
          {([["animal", "띠"], ["zodiac", "별자리"], ["mbti", "MBTI"]] as [FortuneType, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => { setActiveTab(key); setFortune(null); }}
              style={{
                padding: "0.4rem 1rem", borderRadius: "9999px", fontSize: "0.85rem", fontWeight: 500,
                backgroundColor: activeTab === key ? "var(--app-accent)" : "var(--app-card-bg)",
                color: activeTab === key ? "#0E0E2A" : "var(--app-text-muted)",
                border: activeTab === key ? "none" : "1px solid var(--app-border)",
                cursor: "pointer", transition: "all 0.2s",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 운세 카드 — 띠 */}
        {activeTab === "animal" && (
          <FortuneCard
            emoji={animal ? ZODIAC_ANIMAL_EMOJI[animal as keyof typeof ZODIAC_ANIMAL_EMOJI] : "✨"}
            title={animal ? `${animal}띠` : "내 띠 선택"}
            hasValue={!!animal}
            loading={loading}
            fortuneText={fortuneText}
            investTip={investTip}
            stars={stars}
            selector={
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "1rem" }}>
                {ANIMALS.map((a) => (
                  <button
                    key={a}
                    onClick={() => handleAnimalSelect(a)}
                    style={{
                      padding: "0.4rem 0.8rem", borderRadius: "8px",
                      backgroundColor: "var(--app-bg-tertiary)", color: "var(--app-text)", fontSize: "0.85rem", cursor: "pointer",
                    }}
                  >
                    {ZODIAC_ANIMAL_EMOJI[a as keyof typeof ZODIAC_ANIMAL_EMOJI]} {a}
                  </button>
                ))}
              </div>
            }
          />
        )}

        {/* 운세 카드 — 별자리 */}
        {activeTab === "zodiac" && (
          <FortuneCard
            emoji={sign ? ZODIAC_SIGN_EMOJI[sign as keyof typeof ZODIAC_SIGN_EMOJI] : "⭐"}
            title={sign || "내 별자리 선택"}
            hasValue={!!sign}
            loading={loading}
            fortuneText={fortuneText}
            investTip={investTip}
            stars={stars}
            selector={
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "1rem" }}>
                {SIGNS.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSignSelect(s)}
                    style={{
                      padding: "0.4rem 0.8rem", borderRadius: "8px",
                      backgroundColor: "var(--app-bg-tertiary)", color: "var(--app-text)", fontSize: "0.85rem", cursor: "pointer",
                    }}
                  >
                    {ZODIAC_SIGN_EMOJI[s as keyof typeof ZODIAC_SIGN_EMOJI]} {s}
                  </button>
                ))}
              </div>
            }
          />
        )}

        {/* MBTI 카드 */}
        {activeTab === "mbti" && (
          <div style={{
            backgroundColor: "var(--app-card-bg)",
            border: "1px solid var(--app-border)",
            borderLeft: "3px solid var(--app-accent)",
            borderRadius: "12px", padding: "1.5rem",
          }}>
            {mbti ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span style={{ fontSize: "2rem" }}>🧠</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "1.2rem", color: "var(--app-accent)" }}>{mbti}</div>
                    <div style={{ fontSize: "0.85rem", color: "var(--app-text-muted)" }}>{MBTI_INVEST_STYLE[mbti] || "투자 성향"}</div>
                  </div>
                </div>
                <p style={{ color: "var(--app-text-secondary)", marginBottom: "1rem", lineHeight: 1.7 }}>
                  {MBTI_INVEST_STYLE[mbti]} 성향으로, 감정보다 데이터를 신뢰하는 투자가 강점입니다.
                </p>
                <div style={{
                  padding: "0.75rem", backgroundColor: "var(--app-bg-tertiary)",
                  borderRadius: "8px", display: "flex", alignItems: "center", gap: "0.5rem",
                }}>
                  <span style={{ fontSize: "1.2rem" }}>👴</span>
                  <span style={{ fontSize: "0.9rem", color: "var(--app-text-secondary)" }}>
                    닮은 대가: <strong style={{ color: "var(--app-accent)" }}>{MBTI_MASTER[mbti]}</strong>
                  </span>
                </div>
              </>
            ) : (
              <div style={{ textAlign: "center", padding: "1rem 0", color: "var(--app-text-muted)" }}>
                <p style={{ marginBottom: "1rem" }}>MBTI를 입력하면 투자성향이 나타납니다</p>
                <Link
                  href="/settings/profile"
                  style={{
                    display: "inline-block", padding: "0.5rem 1.5rem",
                    backgroundColor: "var(--app-accent)", color: "#0E0E2A",
                    borderRadius: "8px", fontWeight: 600, fontSize: "0.9rem",
                  }}
                >
                  프로필 설정하기
                </Link>
              </div>
            )}
          </div>
        )}

        {/* 뉴스 미리보기 */}
        <div style={{ marginTop: "2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--app-text)" }}>오늘의 뉴스</h2>
            <Link href="/news" style={{ fontSize: "0.8rem", color: "var(--app-accent)" }}>더보기 →</Link>
          </div>
          <div style={{
            backgroundColor: "var(--app-card-bg)", border: "1px solid var(--app-border)",
            borderRadius: "12px", overflow: "hidden",
          }}>
            {news.length > 0 ? news.map((item, i) => (
              <a
                key={i}
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "block",
                  padding: "0.85rem 1rem",
                  borderBottom: i < news.length - 1 ? "1px solid var(--app-border-light)" : "none",
                  fontSize: "0.9rem", color: "var(--app-text-secondary)", lineHeight: 1.5,
                  textDecoration: "none",
                }}
              >
                · {item.title}
              </a>
            )) : (
              <div style={{ padding: "0.85rem 1rem", fontSize: "0.85rem", color: "var(--app-text-muted)" }}>
                <Link href="/news" style={{ color: "var(--app-accent)" }}>뉴스 탭</Link>에서 오늘의 주식 뉴스를 확인하세요
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FortuneCard({
  emoji, title, hasValue, loading, fortuneText, investTip, stars, selector,
}: {
  emoji: string;
  title: string;
  hasValue: boolean;
  loading: boolean;
  fortuneText?: string;
  investTip?: string;
  stars: number;
  selector: React.ReactNode;
}) {
  return (
    <div style={{
      backgroundColor: "var(--app-card-bg)",
      border: "1px solid var(--app-border)",
      borderLeft: "3px solid var(--app-accent)",
      borderRadius: "12px", padding: "1.5rem",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
        <span style={{ fontSize: "2.5rem" }}>{emoji}</span>
        <div>
          <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "var(--app-text)" }}>{title}</div>
          {stars > 0 && (
            <div style={{ display: "flex", gap: "2px", marginTop: "2px" }}>
              {Array.from({ length: 5 }, (_, i) => (
                <span key={i} style={{ color: i < stars ? "#F59E0B" : "var(--app-text-faint)", fontSize: "0.9rem" }}>★</span>
              ))}
              <span style={{ fontSize: "0.75rem", color: "var(--app-text-muted)", marginLeft: "4px" }}>투자 기운</span>
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div style={{ color: "var(--app-text-muted)", fontSize: "0.9rem", padding: "0.5rem 0" }}>운세를 불러오는 중...</div>
      ) : hasValue && fortuneText ? (
        <>
          <p style={{ color: "var(--app-text-secondary)", lineHeight: 1.7, marginBottom: "1rem" }}>{fortuneText}</p>
          {investTip && (
            <div style={{
              padding: "0.6rem 0.9rem", backgroundColor: "var(--app-bg-tertiary)",
              borderRadius: "8px", fontSize: "0.85rem", color: "var(--app-accent)",
            }}>
              💡 {investTip}
            </div>
          )}
        </>
      ) : hasValue ? (
        <div style={{ color: "var(--app-text-muted)", fontSize: "0.9rem" }}>운세 데이터를 불러올 수 없습니다</div>
      ) : (
        <>
          <p style={{ color: "var(--app-text-muted)", fontSize: "0.9rem" }}>선택하면 오늘의 운세가 나타납니다</p>
          {selector}
        </>
      )}
    </div>
  );
}
