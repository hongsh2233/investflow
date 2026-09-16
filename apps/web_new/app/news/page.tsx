"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { News } from "../components/module/news/News";
import { StockTermBox } from "../components/module/stock-term-box";
import { MarketIndexBar } from "../components/module/MarketIndexBar";

function NewsContent() {
  const searchParams = useSearchParams();
  const { status } = useSession();
  const tab = searchParams.get("tab") || "all";

  return (
    <News
      initialTab={tab === "favorite" ? "favorite" : "all"}
      isLoggedIn={status === "authenticated"}
    />
  );
}

export default function NewsPage() {
  return (
    <div className="content__wrap">
      <MarketIndexBar />
      <StockTermBox wrapperStyle={{ margin: "0 0 1.5rem" }} />
      <Suspense fallback={<div style={{ padding: "2rem", textAlign: "center" }}>로딩 중...</div>}>
        <NewsContent />
      </Suspense>
    </div>
  );
}
