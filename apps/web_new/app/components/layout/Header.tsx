"use client";

import { BarChart3, ArrowLeft, Search, User } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useState, useEffect } from "react";
import { navItems } from "@/config/nav";
import styles from "./Header.module.css";

export default function Header() {
    const pathname = usePathname();
    const router = useRouter();
    const { status } = useSession();
    const [pointBalance, setPointBalance] = useState<number | null>(null);
    const [memberGrade, setMemberGrade] = useState<string | null>(null);

    const PAGE_HEADER_TITLES: Record<string, string> = {
        "/faq": "자주하는 질문",
        "/about": "플로우 앱 소개",
        "/settings/profile": "정보 수정",
        "/settings/pin": "간편 비밀번호",
        "/settings/my-stocks": "내 종목 시세",
        "/market": "수급",
    };

    const defaultItem = navItems[0];
    const pageTitle = pathname ? PAGE_HEADER_TITLES[pathname] : undefined;
    const currentItem =
        pageTitle
            ? { ...defaultItem, headerTitle: pageTitle }
            : navItems.find((item) => item.href === pathname) ??
              (pathname?.startsWith("/report") ? navItems.find((item) => item.id === "news") : null) ??
              (pathname?.startsWith("/stocks") ? navItems.find((item) => item.id === "watchlist") : null) ??
              (pathname?.startsWith("/search") ? { ...defaultItem, headerTitle: "검색" } : null) ??
              navItems.find((item) => item.href !== "/" && pathname?.startsWith(item.href)) ??
              defaultItem;

    const isHome = pathname === "/fortune" || pathname === "/" || pathname === "";
    const isNavTab = !isHome && navItems.some((item) => item.href === pathname);

    useEffect(() => {
        if (status !== "authenticated") {
            setPointBalance(null);
            return;
        }
        let cancelled = false;
        fetch("/api/auth/member/info", { cache: "no-store" })
            .then((r) => r.json())
            .then((j) => {
                if (cancelled || typeof j.point_balance !== "number") return;
                setPointBalance(j.point_balance);
                if (j.grade) setMemberGrade(j.grade);
            })
            .catch(() => {});
        return () => { cancelled = true; };
    }, [status]);

    useEffect(() => {
        const onPoints = (e: Event) => {
            const ce = e as CustomEvent<{ balance?: number }>;
            if (typeof ce.detail?.balance === "number") setPointBalance(ce.detail.balance);
        };
        window.addEventListener("memberPointsUpdated", onPoints);
        return () => window.removeEventListener("memberPointsUpdated", onPoints);
    }, []);

    /* ── 홈(투자운세) 헤더 ── */
    if (isHome) {
        return (
            <div className={styles.header__wrap}>
                <div className={styles.topRow}>
                    <div className={styles.logoRow}>
                        <div className={styles.logoIcon}>
                            <BarChart3 className={styles.logoIconSvg} aria-hidden />
                        </div>
                        <span className={styles.logoText}>플로우</span>
                    </div>

                    <div className={styles.rightHeaderCluster}>
                        {status === "authenticated" && pointBalance !== null && memberGrade !== "family" && (
                            <span className={styles.pointBadge} aria-label="보유 포인트">
                                {pointBalance.toLocaleString()} P
                            </span>
                        )}
                        <button
                            className={styles.bellBtn}
                            onClick={() => router.push("/search")}
                            aria-label="검색"
                        >
                            <Search className={styles.bellIcon} aria-hidden />
                        </button>
                        <button
                            className={styles.bellBtn}
                            onClick={() => router.push("/settings")}
                            aria-label="설정/프로필"
                        >
                            <User className={styles.bellIcon} aria-hidden />
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    /* ── 탭 페이지 헤더 (뉴스/관심종목/대가들의 한마디) ── */
    if (isNavTab) {
        return (
            <div className={styles.header__wrap}>
                <div className={styles.subTopRow}>
                    <div style={{ width: "2.5rem" }} />
                    <div className={styles.centerTitle}>
                        <div className={styles.centerTitleIcon}>
                            <BarChart3 className={styles.centerTitleIconSvg} aria-hidden />
                        </div>
                        <span className={styles.centerTitleText}>{currentItem?.headerTitle}</span>
                    </div>
                    <div className={styles.rightHeaderCluster}>
                        {status === "authenticated" && pointBalance !== null && memberGrade !== "family" && (
                            <span className={styles.pointBadge}>{pointBalance.toLocaleString()} P</span>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    /* ── 서브 페이지 헤더 — 뒤로가기 + 타이틀 ── */
    return (
        <div className={styles.header__wrap}>
            <div className={styles.subTopRow}>
                <button
                    className={styles.backBtn}
                    onClick={() => router.back()}
                    aria-label="뒤로가기"
                >
                    <ArrowLeft className={styles.backIcon} aria-hidden />
                </button>

                <div className={styles.centerTitle}>
                    <div className={styles.centerTitleIcon}>
                        <BarChart3 className={styles.centerTitleIconSvg} aria-hidden />
                    </div>
                    <span className={styles.centerTitleText}>{currentItem?.headerTitle}</span>
                </div>

                <div className={styles.rightHeaderCluster}>
                    {status === "authenticated" && pointBalance !== null && memberGrade !== "family" && (
                        <span className={styles.pointBadge}>{pointBalance.toLocaleString()} P</span>
                    )}
                </div>
            </div>
        </div>
    );
}
