import type { NextConfig } from "next";
import path from "path";
import fs from "fs";

// 루트(flow) .env.local 로드 — web·admin 공용
// apps/web에서 실행 시 ../../.env.local, 루트에서 실행 시 .env.local
// dotenv가 없어도 동작하도록 try-catch로 처리
try {
  const dotenv = require("dotenv");
  const rootEnvLocal = path.resolve(process.cwd(), "../../.env.local");
  const rootEnvLocalAlt = path.resolve(process.cwd(), ".env.local");
  
  // 파일이 존재하는 경우에만 로드
  let loaded = false;
  if (fs.existsSync(rootEnvLocal)) {
    dotenv.config({ path: rootEnvLocal, override: false });
    loaded = true;
    if (process.env.NODE_ENV !== 'production') {
      console.log(`[next.config] 루트 .env.local 로드됨: ${rootEnvLocal}`);
    }
  }
  if (fs.existsSync(rootEnvLocalAlt)) {
    dotenv.config({ path: rootEnvLocalAlt, override: false });
    loaded = true;
    if (process.env.NODE_ENV !== 'production') {
      console.log(`[next.config] 로컬 .env.local 로드됨: ${rootEnvLocalAlt}`);
    }
  }
  
  // 디버깅: NEXT_PUBLIC_X_API_KEY 로드 확인 (개발 환경에서만)
  if (process.env.NODE_ENV !== 'production' && !loaded) {
    console.warn("[next.config] .env.local 파일을 찾을 수 없습니다. Next.js 기본 환경 변수 로딩을 사용합니다.");
  }
} catch (error) {
  // dotenv가 설치되지 않은 경우 무시 (Next.js가 기본적으로 .env.local을 로드함)
  console.warn("dotenv 모듈을 찾을 수 없습니다. Next.js 기본 환경 변수 로딩을 사용합니다.");
}

const projectRoot = __dirname;

const nextConfig: NextConfig = {
  output: "standalone",
  async redirects() {
    return [
      {
        source: "/supply",
        destination: "/market",
        permanent: true,
      },
      {
        source: "/market/supply",
        destination: "/market",
        permanent: true,
      },
      {
        source: "/picks",
        destination: "/stocks",
        permanent: true,
      },
    ];
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production'
      ? {
          exclude: ['error', 'warn'],
        }
      : false,
  },
  turbopack: {
    resolveAlias: {
      '@capacitor/push-notifications': './lib/stubs/capacitor-push-stub.ts',
      '@capacitor/core': './lib/stubs/capacitor-core-stub.ts',
    },
  },
  webpack: (config) => {
    config.resolve ??= {};
    config.resolve.alias = {
      ...config.resolve.alias,
      '@capacitor/push-notifications': path.join(projectRoot, 'lib/stubs/capacitor-push-stub.ts'),
      '@capacitor/core': path.join(projectRoot, 'lib/stubs/capacitor-core-stub.ts'),
    };
    return config;
  },
};

export default nextConfig;
