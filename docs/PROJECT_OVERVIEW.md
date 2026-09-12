# Jurin-i (주린이) 프로젝트 개요

**서비스명**: 플로우 (Pflow)
주식 초보 투자자를 위한 종합 주식정보 플랫폼. 모바일(APK) + 웹 지원.
문의: support@jurini.co.kr

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | Next.js 16 + React 19 + TypeScript |
| Backend | FastAPI + SQLAlchemy + PostgreSQL (→ C안 전환 후 Next.js BFF + Prisma) |
| Mobile | Capacitor 7 (Android APK) |
| AI | Google Gemini (🔴 전면 차단 2026-08-03), Anthropic Claude |
| Push | Firebase Cloud Messaging (FCM) |
| State | Zustand |
| Auth | NextAuth (Google OAuth), JWT |
| Scheduler | APScheduler (Python) |
| UI | Tailwind CSS, MUI, Lucide Icons |
| 배포 | Ubuntu 물리 서버 (i7/16GB) + Docker Compose + Nginx Proxy Manager + Cloudflare Tunnel |
| CI/CD | GitHub Actions → SSH 배포 (예정) |

---

## 모노레포 구조

```
Jurin-i/                         ← 현재 구조
├── apps/
│   ├── web_new/          # Next.js 프론트엔드 (사용자향)  →  apps/web/ 로 이전 예정
│   └── admin/            # FastAPI 백엔드 (관리자 + API)  →  apps/scheduler/ 로 분리 예정
├── packages/
│   ├── database/         # Prisma 스키마  →  apps/web/prisma/ 로 이동 예정
│   └── ui/               # 공유 UI 컴포넌트 (내용 없음, 삭제 예정)
├── archive/              # Gemini 코드 아카이브 (C안 마이그레이션 시 생성)
└── docs/                 # 프로젝트 문서

# C안 전환 후 목표 구조:
# apps/web/        ← Next.js (BFF: Server Actions + Prisma 직접 접근)
# apps/scheduler/  ← Python 전담 (스케줄러 + BO 대시보드, 내부망 전용)
```

> **아키텍처 전환 방향**: `docs/architecture-migration-plan.md` 참조

---

## IA (Information Architecture)

### 프론트엔드 페이지 구조 (web_new)

```
/ (홈)
├── /market              # 종목 검색
│   └── /supply          # 수급 현황
├── /stocks              # 주식 목록
│   └── /search          # 종목 검색
├── /briefing            # 뉴스·시황 브리핑
├── /news                # 뉴스
├── /calendar            # 일정 캘린더
├── /report              # 리포트
│   └── /[id]            # 리포트 상세
├── /board               # 게시판
│   ├── /[id]            # 게시글 상세
│   └── /write           # 게시글 작성
├── /stock-chat          # 주톡 (채팅)
├── /supply              # 수급 정보
├── /login               # 로그인
│   ├── /find-id         # 아이디 찾기
│   └── /find-password   # 비밀번호 찾기
├── /signup              # 회원가입
├── /settings            # 설정
│   ├── /pin             # PIN 설정
│   └── /profile         # 프로필 설정
├── /faq                 # FAQ
└── /about               # 소개
```

### 주요 컴포넌트 구조

```
components/
├── layout/
│   ├── Header.tsx                # 헤더
│   ├── BottomNavigation.tsx      # 하단 네비게이션
│   └── LayoutShell.tsx           # 레이아웃 셸
├── module/
│   ├── HomeGreeting.tsx          # 홈 인사말
│   ├── BannerSection.tsx         # 배너 섹션
│   ├── MarketIndexSection.tsx    # 시장 지수
│   ├── InvestorTrendChart.tsx    # 투자자 동향 차트
│   ├── FavoriteStocks.tsx        # 관심종목
│   ├── TradeRankingSection.tsx   # 거래 랭킹
│   ├── NewsL.tsx / AllNews.tsx   # 뉴스 섹션
│   ├── StockDetailModal.tsx      # 종목 상세 모달
│   ├── PopupModal.tsx            # 팝업 모달
│   ├── SchedulePopup.tsx         # 일정 팝업
│   ├── MarketSummaryPopup.tsx    # 아침 시장 요약
│   ├── FloatingButtons.tsx       # 플로팅 버튼 (주식용어사전)
│   ├── StockTermBox.tsx          # 주식용어 박스
│   ├── AdBanner.tsx              # 광고 배너
│   └── AppDownloadModal.tsx      # 앱 다운로드 안내
├── ui/
│   ├── BottomSheet.tsx           # 바텀시트
│   ├── Button.tsx                # 버튼
│   ├── TermsModal.tsx            # 약관 모달
│   └── PinKeypad.tsx             # PIN 키패드
└── providers/
    ├── NextAuthProvider.tsx       # 인증 프로바이더
    ├── CapacitorProvider.tsx      # 모바일 프로바이더
    └── ThemeProvider.tsx          # 테마 프로바이더
```

### API 라우트 (web_new/app/api)

| 카테고리 | 엔드포인트 | 설명 |
|----------|-----------|------|
| 인증 | `/api/auth/[...nextauth]` | NextAuth (Google/Naver) |
| 시장 | `/api/domestic-indices`, `/api/foreign-indices` | 국내/해외 지수 |
| 환율 | `/api/exchange-rate` | 환율 정보 |
| 종목 | `/api/fsc-stock-price`, `/api/fsc-rising-stocks` | FSC 주가/급등주 |
| 네이버 | `/api/naver-ranking`, `/api/naver-news`, `/api/naver-investor-trend` | 네이버 금융 데이터 |
| 뉴스 | `/api/naver-stock-news`, `/api/daily-issue-summary` | 종목뉴스/이슈요약 |
| 수급 | `/api/naver-supply`, `/api/supply-summary` | 수급 데이터 |
| 일정 | `/api/schedules`, `/api/schedule-alarms` | 일정/알림 |
| 게시판 | `/api/boards`, `/api/posts` | 게시판 |
| 투표 | `/api/polls`, `/api/poll-vote`, `/api/poll-stats` | 투표 |
| 주식용어 | `/api/stock-terms` | 주식용어사전 |
| 배너 | `/api/banners`, `/api/popups` | 배너/팝업 |
| 기타 | `/api/market-morning-summary`, `/api/market-voices` | AI 요약/대가의 한마디 |

---

### 백엔드 구조 (admin)

#### 라우터 (22개)

| 라우터 | 설명 |
|--------|------|
| `auth.py` | 로그인/회원가입/소셜인증 |
| `dashboard.py` | 대시보드 데이터 |
| `finance.py` | 금융 데이터 API |
| `api.py` | 일반 API (스크리닝, 관심종목 등) |
| `board.py` | 게시판 관리 |
| `members.py` | 회원 관리 |
| `schedule.py` | 일정 관리 |
| `polls.py` | 투표 관리 |
| `faq.py` | FAQ 관리 |
| `popup.py` | 팝업 관리 |
| `stock_terms.py` | 주식용어 관리 |
| `market_voices.py` | 대가의 한마디 |
| `master_quotes.py` | 명언 관리 |
| `ad_settings.py` | 광고 설정 |
| `fsc.py` | 금융위 데이터 |
| `investment_bank_news.py` | 증권사 리포트 |
| `target_price_news.py` | 목표가 뉴스 |
| `terms.py` | 이용약관/개인정보 |
| `profile.py` | 프로필 |
| `admin.py` | 관리자 설정 |
| `broker.py` | 증권사 설정 |

#### 서비스 (25개)

| 서비스 | 설명 |
|--------|------|
| `naver_finance_service.py` | 네이버 금융 크롤링 |
| `naver_news_service.py` | 네이버 뉴스 크롤링 |
| `naver_rising_stock_service.py` | 급등주 수집 |
| `naver_supply_service.py` | 수급 데이터 수집 |
| `yahoo_index_service.py` | Yahoo 지수 수집 |
| `exchange_rate_service.py` | 환율 수집 |
| `investing_com_service.py` | Investing.com 데이터 |
| `stock_screening_service.py` | 일목균형표 스크리닝 |
| `jongbe_screening_service.py` | 종가베팅 스크리닝 |
| `screening_progress.py` | 스크리닝 진행상태 |
| `daily_issue_gemini_service.py` | 일간 이슈 AI 요약 |
| `market_morning_gemini_service.py` | 아침 시장 AI 요약 |
| `market_closing_gemini_service.py` | 마감 시장 AI 요약 |
| `supply_summary_gemini_service.py` | 수급 AI 요약 |
| `fcm_service.py` | FCM 푸시 알림 |
| `push_service.py` | 푸시 서비스 |
| `scheduler_service.py` | 스케줄러 관리 |
| `market_voice_service.py` | 대가의 한마디 |
| `api_service.py` | 외부 API 연동 |
| `investment_bank_news_service.py` | 증권사 뉴스 크롤링 |
| `target_price_news_service.py` | 목표가 뉴스 크롤링 |
| `opendart_ipo_service.py` | OpenDART IPO 정보 |
| `schedule_api_service.py` | 일정 API |
| `gemini_response_utils.py` | Gemini 유틸리티 |

#### DB 모델 (47개)

핵심 모델: `Member`, `AdminUser`, `Post`, `Board`, `Poll`, `Schedule`, `Banner`, `Popup`, `Notification`, `StockScreeningResult`, `JongbeScreeningResult`, `NaverStockRanking`, `MarketMorningAiSummary`, `StockTerm`, `FscStockPrice` 등

#### 관리자 대시보드 (45개 템플릿)

Jinja2 기반 관리자 페이지: 회원관리, 게시판관리, 배너/팝업관리, 금융데이터, 일정관리, FAQ, 스톡스크리닝 등

---

## 1차 개발 완료 기능 목록

### 사용자 기능 (Frontend)

1. **홈 화면**: 인사말, 배너, 시장지수, 투자자동향 차트, 관심종목, 거래랭킹, 뉴스
2. **종목 검색/상세**: FSC 주가 데이터, 네이버 뉴스 연동, 관심종목 추가/삭제
3. **뉴스·시황**: 네이버 뉴스, AI 일간이슈 요약, 증권사 리포트
4. **수급 정보**: 기관/외국인 수급 현황, AI 수급 요약
5. **일정 캘린더**: IPO, 배당, 실적발표 일정 + 알림 구독
6. **게시판/주톡**: 커뮤니티 게시판, 주식 채팅
7. **투표**: 오늘의 투표 기능
8. **주식용어사전**: 플로팅 버튼 + 바텀시트 검색
9. **아침 시장 브리핑**: KST 06:00~08:50 자동 팝업 + FCM 알림
10. **앱 다운로드 안내**: 모바일웹 접속 시 앱 설치 유도

### 관리자 기능 (Backend/Dashboard)

1. **대시보드**: 회원 통계, 게시글 통계
2. **자동 데이터 수집**: 스케줄러 기반 (네이버, Yahoo, 환율, FSC 등)
3. **AI 요약 생성**: Gemini 기반 아침/마감/이슈/수급 요약
4. **일목균형표 스크리닝**: 조건검색 + 수동실행 + 진행상태 표시
5. **종가베팅 스크리닝**: 8개 조건 (시총, 거래대금, 등락률, 양봉, 고가비율, 5MA, RSI, 거래량) + 병렬처리
6. **배너/팝업 관리**: HTML/이미지/텍스트 배너, 팝업 등록/수정
7. **게시판/FAQ/약관 관리**: CRUD + 카테고리
8. **FCM 푸시 알림**: 일정 알림, 아침 브리핑 알림

---

## 외부 서비스 연동 현황

| 서비스 | 제공사 | 용도 | 활성 여부 |
|--------|--------|------|----------|
| Google OAuth | Google LLC (미국) | 소셜 로그인 | ✅ 활성 |
| Naver OAuth | Naver Corp (한국) | 소셜 로그인 | ❌ 비활성 |
| Kakao OAuth | Kakao Corp (한국) | 소셜 로그인 | ❌ 비활성 |
| Firebase FCM | Google LLC (미국) | 푸시 알림 | ✅ 활성 |
| Google Gemini 2.5 Flash | Google LLC (미국) | AI 요약·분석 | 🔴 전면 차단 (2026-08-03) |
| Google AdSense | Google LLC (미국) | 광고 수익 (ca-pub-6042624006544756) | ✅ 활성 |
| Google Tag Manager | Google LLC (미국) | 이용 분석 (GTM-52KM4V3R) | ✅ 활성 |
| Yahoo Finance | Yahoo Inc (미국) | 국내외 지수, 환율 | ✅ 활성 |
| Naver Search API | Naver Corp (한국) | 뉴스, 수급 데이터 | ✅ 활성 |
| FSC (금융감독원) | 금융위원회 (한국) | 주가 데이터 | ✅ 활성 |
| KRX (한국거래소) | KRX (한국) | 시장 데이터 | ✅ 활성 |
| OpenDART | 금융감독원 (한국) | IPO·공시 정보 | ✅ 활성 |
| data.go.kr | 공공데이터포털 (한국) | 공휴일 데이터 | ✅ 활성 |
| Railway | Railway Inc (미국) | 서버·DB 호스팅 | 🔴 제거 예정 (자체 서버로 이전) |
| Resend | Resend Inc (미국) | 이메일 발송 | ✅ 활성 |
| AliExpress 제휴 | Alibaba Group (중국) | 제휴 광고 상품 | ✅ 활성 |

## 수집·처리 개인정보 항목

| 항목 | 수집 시점 | 저장 위치 |
|------|----------|----------|
| 이메일 | 회원가입 | `members.email` |
| 비밀번호 (Bcrypt 암호화) | 회원가입 | `members.hashed_password` |
| 닉네임 | 회원가입 (자동 생성 가능) | `members.nickname` |
| 프로필 이미지 URL | 소셜 로그인 또는 직접 설정 | `members.profile_image` |
| Google provider_id | 소셜 로그인 | `members.provider_id` |
| FCM 기기 토큰 | 앱 설치 시 | `member_fcm_tokens.token` |
| 관심종목 목록 | 사용자 추가 시 | `members.favorite_stocks` (JSON) |
| 주BTI 성향 (A/D/N/I) | 테스트 완료 시 | `members.jubti_type` |
| 접속 IP | 로그인 시 | 로그인 실패 기록 (15분 보관) |
| 서비스 이용 행태 | 페이지 방문 시 | Google Tag Manager (GTM-52KM4V3R) |

## 보안 설정

| 항목 | 방식 |
|------|------|
| 비밀번호 암호화 | Bcrypt (salt 자동 생성) |
| Access Token | JWT HS256, 만료 1시간 |
| Refresh Token | JWT HS256, 만료 30일 |
| API 인증 | X-API-KEY 헤더 |
| 로그인 실패 제한 | 5회 실패 → 15분 잠금 (IP 기반) |
| 관리자 세션 | 쿠키 기반, 비활성 10분 / 최대 30분 |
| HTTPS | Cloudflare SSL (자체 서버 Cloudflare Tunnel 경유) |

## 회원 등급 체계

| 등급 | 코드 | 설명 |
|------|------|------|
| 일반 | `regular` | 기본 등급 (기본값) |
| VIP | `vip` | 프리미엄 회원 (기간 설정 가능) |
| 패밀리 | `family` | 그룹 회원 (기간 설정 가능) |

등급 만료 시 자동으로 `regular`로 복귀 (`get_effective_grade()` 함수).

## 데이터 자동 수집 스케줄 (평일 기준, KST)

| 데이터 | 수집 시각 | 소스 |
|--------|----------|------|
| 아침 AI 브리핑 | 06:35 | Yahoo/Naver (Gemini 차단, AI 요약 비활성) |
| 목표가 상향 뉴스 | 08:30, 12:00 | Naver (Gemini 파싱 차단, 원문 저장) |
| 수급 동향 | 08:40~15:40 (30분 간격), 16:40~20:40 (1시간 간격) | Naver 증권 |
| 일간 이슈 AI 요약 | 08:40, 12:40, 19:40 | 🔴 Gemini 차단으로 비활성 |
| 주식 영향 뉴스 | 08:30, 12:30, 19:30 | Naver 뉴스 |
| 종가베팅 스크리닝 | 15:00 | 자체 엔진 |
| 마감 AI 요약 | 15:50 | 🔴 Gemini 차단으로 비활성 |
| 일목균형표 스크리닝 | 20:30 | 자체 엔진 |
| 코스피/코스닥 지수 | 09:10~15:10 (30분), 15:40 | Yahoo Finance |
| 해외 지수 | 장전·장중 수회 | Yahoo Finance |
| 환율 | 30분마다 | Yahoo Finance |

## 법률 문서 현황

| 문서 | 관리 경로 | 참조 파일 |
|------|----------|----------|
| 개인정보처리방침 | `/admin/terms/privacy` | `docs/개인정보처리방침.md` |
| 이용약관 | `/admin/terms/service` | `docs/이용약관.md` |
| 앱 소개 | `/admin/terms/about` | - |
| API 제공 경로 | `/api/legal-documents/{privacy\|terms\|about}` | - |

---

## 로컬 개발 환경

```bash
# 1. DB (Docker)
cd apps/admin && docker-compose up -d

# 2. Backend
cd apps/admin
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# 3. Frontend
cd apps/web_new        # C안 이전 후: apps/web
npm install && npm run dev

# 접속:
# - 웹앱: http://localhost:3000
# - API: http://localhost:8080  (C안 이전 후 제거)
# - 관리자(BO): http://localhost:8001  (C안 이전 후 내부망 전용)
# - API 문서: http://localhost:8080/docs  (C안 이전 후 제거)
```
