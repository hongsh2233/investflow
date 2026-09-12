import type { Metadata } from "next";

export const SITE_NAME = "플로우";

export const SITE_DESCRIPTION =
  "투자자를 위한 운세·뉴스·관심종목 앱. 투자운세, 주식뉴스, 관심종목 관리를 모바일에서 간편하게 이용하세요.";

const DEFAULT_KEYWORDS = [
  "플로우",
  "주식",
  "투자",
  "주린이",
  "주식앱",
  "브리핑",
  "한국주식",
  "모바일",
];

function canonicalSiteUrl(): string | undefined {
  const raw =
    process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
    process.env.NEXTAUTH_URL?.trim() ||
    "";
  if (!raw) return undefined;
  return raw.replace(/\/$/, "");
}

function metadataBaseUrl(): URL | undefined {
  const base = canonicalSiteUrl();
  if (!base) return undefined;
  try {
    return new URL(base.endsWith("/") ? base : `${base}/`);
  } catch {
    return undefined;
  }
}

/** 루트 layout용 SEO·SNS 메타 (페이지별 metadata는 각 page에서 덮어쓰기 가능) */
export function buildRootMetadata(): Metadata {
  const baseUrl = canonicalSiteUrl();
  const metadataBase = metadataBaseUrl();

  const openGraph: Metadata["openGraph"] = {
    type: "website",
    locale: "ko_KR",
    siteName: SITE_NAME,
    title: SITE_NAME,
    description: SITE_DESCRIPTION,
    ...(baseUrl
      ? {
          url: baseUrl,
          images: [
            {
              url: "/images/icon-512.png",
              width: 512,
              height: 512,
              alt: SITE_NAME,
            },
          ],
        }
      : {
          images: [{ url: "/images/icon-512.png", width: 512, height: 512, alt: SITE_NAME }],
        }),
  };

  const metadata: Metadata = {
    ...(metadataBase ? { metadataBase } : {}),
    title: {
      default: SITE_NAME,
      template: `%s | ${SITE_NAME}`,
    },
    description: SITE_DESCRIPTION,
    applicationName: SITE_NAME,
    keywords: DEFAULT_KEYWORDS,
    authors: [{ name: SITE_NAME }],
    creator: SITE_NAME,
    formatDetection: {
      telephone: false,
    },
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        "max-image-preview": "large",
        "max-snippet": -1,
      },
    },
    openGraph,
    twitter: {
      card: "summary_large_image",
      title: SITE_NAME,
      description: SITE_DESCRIPTION,
      images: ["/images/icon-512.png"],
    },
    alternates: baseUrl ? { canonical: baseUrl } : undefined,
  };

  const verify = process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION?.trim();
  if (verify) {
    metadata.verification = { google: verify };
  }

  return metadata;
}
