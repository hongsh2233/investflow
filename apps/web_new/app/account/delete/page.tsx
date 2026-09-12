"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { withdrawMember } from "@/lib/services/authService";

export default function AccountDeletePage() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const [step, setStep] = useState<"info" | "confirm" | "done">("info");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isLoggedIn = status === "authenticated";

  async function handleDelete() {
    if (!session?.user?.email) return;
    setLoading(true);
    setError("");
    try {
      const result = await withdrawMember(session.user.email);
      if (result.success) {
        setStep("done");
        await signOut({ redirect: false });
      } else {
        setError(result.message ?? "회원 탈퇴에 실패했습니다. 다시 시도해주세요.");
      }
    } catch {
      setError("오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      backgroundColor: "var(--app-bg)",
      padding: "0 0 4rem",
    }}>
      {/* 헤더 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "1rem",
        borderBottom: "1px solid var(--app-border)",
      }}>
        <button
          onClick={() => router.back()}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontSize: "1.25rem",
            color: "var(--app-text)",
            padding: "0.25rem",
          }}
        >
          ←
        </button>
        <h1 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "var(--app-text)" }}>
          계정 삭제
        </h1>
      </div>

      <div style={{ padding: "1.5rem 1rem", maxWidth: "480px", margin: "0 auto" }}>

        {step === "info" && (
          <>
            {/* 안내 박스 */}
            <div style={{
              backgroundColor: "var(--app-surface-elevated)",
              borderRadius: "12px",
              padding: "1.5rem",
              marginBottom: "1.5rem",
            }}>
              <div style={{ fontSize: "2rem", marginBottom: "0.75rem", textAlign: "center" }}>⚠️</div>
              <h2 style={{
                fontSize: "1rem",
                fontWeight: 700,
                color: "var(--app-text)",
                marginBottom: "1rem",
                textAlign: "center",
              }}>
                계정을 삭제하기 전에 확인하세요
              </h2>
              <ul style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}>
                {[
                  "모든 개인 정보가 영구적으로 삭제됩니다",
                  "관심종목, 투자 기록 등 저장된 데이터가 삭제됩니다",
                  "삭제된 계정은 복구할 수 없습니다",
                  "동일한 이메일로 재가입은 가능합니다",
                ].map((item, i) => (
                  <li key={i} style={{
                    display: "flex",
                    gap: "0.5rem",
                    fontSize: "0.88rem",
                    color: "var(--app-text-muted)",
                    lineHeight: 1.5,
                  }}>
                    <span style={{ color: "#ef4444", flexShrink: 0 }}>•</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* 삭제 방법 */}
            <div style={{
              backgroundColor: "var(--app-card-bg)",
              borderRadius: "12px",
              padding: "1.25rem",
              marginBottom: "1.5rem",
              border: "1px solid var(--app-border)",
            }}>
              <h3 style={{
                fontSize: "0.9rem",
                fontWeight: 700,
                color: "var(--app-text)",
                marginBottom: "0.75rem",
              }}>
                삭제 방법
              </h3>
              {isLoggedIn ? (
                <p style={{ fontSize: "0.85rem", color: "var(--app-text-muted)", lineHeight: 1.6, margin: 0 }}>
                  아래 <strong style={{ color: "var(--app-text)" }}>"계정 삭제 진행"</strong> 버튼을 눌러 즉시 계정을 삭제할 수 있습니다.
                </p>
              ) : (
                <p style={{ fontSize: "0.85rem", color: "var(--app-text-muted)", lineHeight: 1.6, margin: 0 }}>
                  앱에서 로그인 후 <strong style={{ color: "var(--app-text)" }}>설정 → 회원 탈퇴</strong>를 통해 계정을 삭제하거나,
                  아래 이메일로 삭제 요청을 보내주세요.
                </p>
              )}
            </div>

            {/* 이메일 요청 */}
            <div style={{
              backgroundColor: "var(--app-card-bg)",
              borderRadius: "12px",
              padding: "1.25rem",
              marginBottom: "1.5rem",
              border: "1px solid var(--app-border)",
            }}>
              <h3 style={{
                fontSize: "0.9rem",
                fontWeight: 700,
                color: "var(--app-text)",
                marginBottom: "0.5rem",
              }}>
                이메일로 삭제 요청
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--app-text-muted)", lineHeight: 1.6, margin: "0 0 0.75rem" }}>
                로그인 없이 삭제를 원하시면 아래 이메일로 요청하세요. (영업일 기준 3일 이내 처리)
              </p>
              <a
                href="mailto:hongsh220303@gmail.com?subject=계정 삭제 요청&body=이름:%0A가입 이메일:%0A삭제 사유:"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.6rem 1rem",
                  backgroundColor: "var(--app-surface-elevated)",
                  border: "1px solid var(--app-border)",
                  borderRadius: "8px",
                  fontSize: "0.88rem",
                  color: "var(--app-accent)",
                  fontWeight: 600,
                  textDecoration: "none",
                }}
              >
                📧 hongsh220303@gmail.com
              </a>
            </div>

            {/* 버튼 영역 */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {isLoggedIn && (
                <button
                  onClick={() => setStep("confirm")}
                  style={{
                    width: "100%",
                    padding: "0.9rem",
                    borderRadius: "10px",
                    backgroundColor: "#ef4444",
                    color: "#fff",
                    fontWeight: 700,
                    fontSize: "0.95rem",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  계정 삭제 진행
                </button>
              )}
              <button
                onClick={() => router.push("/")}
                style={{
                  width: "100%",
                  padding: "0.9rem",
                  borderRadius: "10px",
                  backgroundColor: "var(--app-card-bg)",
                  color: "var(--app-text-muted)",
                  fontWeight: 600,
                  fontSize: "0.95rem",
                  border: "1px solid var(--app-border)",
                  cursor: "pointer",
                }}
              >
                취소
              </button>
            </div>
          </>
        )}

        {step === "confirm" && (
          <>
            <div style={{
              backgroundColor: "#fef2f2",
              border: "1px solid #fca5a5",
              borderRadius: "12px",
              padding: "1.5rem",
              marginBottom: "1.5rem",
              textAlign: "center",
            }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🗑️</div>
              <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "#dc2626", marginBottom: "0.5rem" }}>
                정말 계정을 삭제하시겠습니까?
              </h2>
              <p style={{ fontSize: "0.85rem", color: "#b91c1c", margin: 0, lineHeight: 1.6 }}>
                <strong>{session?.user?.email}</strong> 계정의<br />
                모든 데이터가 영구 삭제됩니다.
              </p>
            </div>

            {error && (
              <div style={{
                backgroundColor: "#fef2f2",
                border: "1px solid #fca5a5",
                borderRadius: "8px",
                padding: "0.75rem 1rem",
                marginBottom: "1rem",
                fontSize: "0.85rem",
                color: "#dc2626",
              }}>
                {error}
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <button
                onClick={handleDelete}
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "0.9rem",
                  borderRadius: "10px",
                  backgroundColor: loading ? "#fca5a5" : "#ef4444",
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: "0.95rem",
                  border: "none",
                  cursor: loading ? "not-allowed" : "pointer",
                }}
              >
                {loading ? "처리 중..." : "네, 계정을 삭제합니다"}
              </button>
              <button
                onClick={() => setStep("info")}
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "0.9rem",
                  borderRadius: "10px",
                  backgroundColor: "var(--app-card-bg)",
                  color: "var(--app-text-muted)",
                  fontWeight: 600,
                  fontSize: "0.95rem",
                  border: "1px solid var(--app-border)",
                  cursor: "pointer",
                }}
              >
                취소
              </button>
            </div>
          </>
        )}

        {step === "done" && (
          <div style={{ textAlign: "center", padding: "3rem 1rem" }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>✅</div>
            <h2 style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              color: "var(--app-text)",
              marginBottom: "0.75rem",
            }}>
              계정이 삭제되었습니다
            </h2>
            <p style={{
              fontSize: "0.88rem",
              color: "var(--app-text-muted)",
              lineHeight: 1.6,
              marginBottom: "2rem",
            }}>
              이용해 주셔서 감사합니다.<br />
              모든 개인 정보가 삭제되었습니다.
            </p>
            <button
              onClick={() => router.push("/")}
              style={{
                padding: "0.9rem 2rem",
                borderRadius: "10px",
                backgroundColor: "var(--app-accent)",
                color: "#0E0E2A",
                fontWeight: 700,
                fontSize: "0.95rem",
                border: "none",
                cursor: "pointer",
              }}
            >
              홈으로 이동
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
