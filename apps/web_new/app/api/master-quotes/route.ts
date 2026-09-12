import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL, API_SECRET_KEY } from "@/lib/config/api";

/**
 * 대가들의 한마디 - Admin API 프록시 (CORS 문제 방지)
 * stock-chat 페이지에서 사용
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const qs = searchParams.toString();

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (API_SECRET_KEY) {
      headers["X-API-KEY"] = API_SECRET_KEY;
    }

    const url = `${API_BASE_URL}/api/master-quotes${qs ? `?${qs}` : ""}`;
    const response = await fetch(url, {
      method: "GET",
      headers,
      cache: "no-store",
    });

    if (!response.ok) {
      return NextResponse.json(
        { items: [] },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("대가들의 한마디 조회 오류:", error);
    return NextResponse.json(
      { items: [] },
      { status: 500 }
    );
  }
}
