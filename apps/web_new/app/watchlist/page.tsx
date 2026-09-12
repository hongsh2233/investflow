"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import Star from "@mui/icons-material/Star";
import AddCircleOutline from "@mui/icons-material/AddCircleOutline";

export default function WatchlistPage() {
  const { status } = useSession();
  const isLoggedIn = status === "authenticated";

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--app-bg)", padding: "0 0 6rem" }}>
      {/* 헤더 */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "1rem",
        borderBottom: "1px solid var(--app-border)",
        backgroundColor: "var(--app-card-bg)",
      }}>
        <h1 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--app-text)" }}>관심종목</h1>
        <button
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.25rem",
            padding: "0.4rem 0.8rem",
            backgroundColor: "var(--app-accent)",
            color: "#0E0E2A",
            borderRadius: "8px",
            fontWeight: 600,
            fontSize: "0.85rem",
            cursor: "pointer",
          }}
        >
          <AddCircleOutline style={{ fontSize: "1rem" }} />
          추가
        </button>
      </div>

      <div style={{ padding: "1.5rem 1rem" }}>
        {!isLoggedIn ? (
          /* 비로그인 상태 */
          <div style={{
            textAlign: "center",
            padding: "3rem 1rem",
            backgroundColor: "var(--app-card-bg)",
            borderRadius: "16px",
            border: "1px solid var(--app-border)",
          }}>
            <Star style={{ fontSize: "3rem", color: "var(--app-accent)", marginBottom: "1rem" }} />
            <h2 style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--app-text)", marginBottom: "0.5rem" }}>
              관심종목 저장
            </h2>
            <p style={{ color: "var(--app-text-muted)", fontSize: "0.9rem", marginBottom: "1.5rem", lineHeight: 1.6 }}>
              로그인하면 관심종목을 저장하고<br />
              뉴스, 목표가 변경을 한눈에 확인할 수 있어요
            </p>
            <Link
              href="/login"
              style={{
                display: "inline-block",
                padding: "0.65rem 2rem",
                backgroundColor: "var(--app-accent)",
                color: "#0E0E2A",
                borderRadius: "8px",
                fontWeight: 700,
                fontSize: "0.95rem",
                textDecoration: "none",
              }}
            >
              로그인하기
            </Link>
          </div>
        ) : (
          /* 로그인 + 빈 상태 */
          <div style={{
            textAlign: "center",
            padding: "4rem 1rem",
            backgroundColor: "var(--app-card-bg)",
            borderRadius: "16px",
            border: "1px dashed var(--app-border)",
          }}>
            <Star style={{ fontSize: "3rem", color: "var(--app-text-muted)", marginBottom: "1rem" }} />
            <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--app-text)", marginBottom: "0.5rem" }}>
              아직 관심종목이 없어요
            </h2>
            <p style={{ color: "var(--app-text-muted)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
              종목을 추가하면 뉴스와 목표가 변경을 알려드려요
            </p>
            <button
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.65rem 1.5rem",
                backgroundColor: "var(--app-accent)",
                color: "#0E0E2A",
                borderRadius: "8px",
                fontWeight: 700,
                fontSize: "0.9rem",
                cursor: "pointer",
              }}
            >
              <AddCircleOutline style={{ fontSize: "1.1rem" }} />
              종목 추가하기
            </button>
          </div>
        )}

        {/* 킬러 기능 안내 */}
        <div style={{ marginTop: "1.5rem" }}>
          <h3 style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--app-text-muted)", marginBottom: "0.75rem" }}>
            관심종목에서 확인할 수 있어요
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {[
              ["📰", "관련 뉴스 모아보기", "keyword 필터로 내 종목 뉴스만"],
              ["🎯", "목표가 상향/하향 알림", "\"OO증권 삼성전자 목표가 9만원 상향\""],
              ["📊", "스크리닝 신호", "이치모쿠 등 기술적 신호 발생 알림"],
            ].map(([icon, title, desc]) => (
              <div
                key={title}
                style={{
                  display: "flex",
                  gap: "0.75rem",
                  padding: "0.85rem",
                  backgroundColor: "var(--app-card-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--app-border)",
                }}
              >
                <span style={{ fontSize: "1.3rem" }}>{icon}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "var(--app-text)" }}>{title}</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--app-text-muted)", marginTop: "2px" }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
