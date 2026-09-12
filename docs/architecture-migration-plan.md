# Jurin-i 아키텍처 전환 계획 (C안: Next.js BFF)

**작성일**: 2026-08-24  
**상태**: 계획 확정 (Phase 0 진행 중)  
**목표**: FastAPI REST 레이어 제거 → Next.js Prisma BFF + Python 스케줄러 전담

---

## 배경 및 목표

### 현재 구조의 문제
- 모든 요청이 `Next.js → FastAPI → DB` 3단계를 거침 (40개+ 프록시 라우트)
- DB 스키마가 SQLAlchemy / Prisma 양쪽에 이중으로 존재
- Railway 종속 배포 → 자체 서버(Ubuntu i7/16GB)로 이전 예정

### 목표 구조
```
Next.js (BFF) ──Prisma──▶ PostgreSQL ◀──SQLAlchemy── Python Scheduler
     ↕                                                      ↕
   사용자                                           BO 대시보드 (내부망)
```

---

## 서버 환경

| 항목 | 내용 |
|------|------|
| 서버 | Ubuntu 물리 서버 (Intel i7 / RAM 16GB) |
| 컨테이너 | Docker Compose |
| 라우팅 | Nginx Proxy Manager |
| 외부 연결 | Cloudflare Tunnel (포트 포워딩 불필요) |
| SSL | Cloudflare 처리 |
| CI/CD | GitHub Actions → SSH |

---

## 목표 디렉토리 구조

```
Jurin-i/
  apps/
    web/                        ← Next.js BFF (현 web_new)
      app/
      prisma/                   ← 스키마 + 마이그레이션 (packages/database에서 이동)
    scheduler/                  ← Python 전담 (현 admin에서 REST 제거)
      services/                 ← 수집 + 스크리닝 + FCM
      dashboard/                ← BO Jinja2 (내부망 전용, http://bo.내부)
      engine/                   ← SQLAlchemy 모델
      scheduler.py
  archive/
    gemini-services/            ← Gemini 코드 보관 (삭제 아님)
  docker-compose.prod.yml
  .github/workflows/deploy.yml
```

---

## 마이그레이션 Phase

### Phase 0 — 기획서 정리 ✅ 완료 (2026-08-24)
- `gemini-removal-migration-guide.md` — 2026-08-03 추가 차단분 반영
- `PROJECT_OVERVIEW.md` — 기술 스택 + 서버 환경 업데이트
- `playground-redesign-plan.md` — 경로 표기 안내 추가
- `architecture-migration-plan.md` — 신규 작성 (이 문서)

---

### Phase 1 — 디렉토리 재편 + Gemini 아카이브

**소요 시간**: 1주  
**범위**: 코드 동작 변경 없음. 구조 정리만.

#### 1-1. Gemini 서비스 아카이브
`archive/gemini-services/` 생성 후 이동:
- `apps/admin/app/services/daily_fortune_gemini_service.py`
- `apps/admin/app/services/daily_issue_gemini_service.py`
- `apps/admin/app/services/supply_summary_gemini_service.py`
- `apps/admin/app/services/market_closing_gemini_service.py`
- `apps/admin/app/services/gemini_response_utils.py`
- `apps/web_new/app/api/mbti-investment-advice/route.ts`
- `apps/web_new/app/api/jubti-strategy/route.ts`

심리지수 관련(`community_sentiment_service.py`, `sentiment_analysis_service.py`) — 비활성 상태로 `apps/scheduler/services/`에 유지.

#### 1-2. 디렉토리 이름 변경
```
apps/admin   → apps/scheduler
apps/web_new → apps/web
packages/database/prisma → apps/web/prisma
packages/ui  → 삭제
```

Railway 설정 파일 제거: `apps/*/railway.json`

---

### Phase 2 — Prisma 스키마 완성 + Next.js API 이전

**소요 시간**: 2-3주  
**범위**: Next.js 40개+ 프록시 라우트를 Prisma 직접 쿼리로 전환.

#### 2-1. Prisma 스키마 동기화
SQLAlchemy 모델(`apps/admin/app/models.py` + `engine/models.py`) 기준으로 Prisma 스키마 완성.

우선 동기화 테이블:
- `Member`, `AdminUser`, `Board`, `Post`, `Poll`, `PollVote`
- `StockTerm`, `MasterQuote`, `MasterQuoteLike`
- `NaverStockNews`, `TargetPriceNews`, `InvestmentBankNews`
- `DailyFortune`, `SupplySummaryAi`, `MarketVoice`
- `Schedule`, `ScheduleAlarm`, `FcmToken`
- 스크리닝 결과 테이블 (Picks 관련)

#### 2-2. Next.js Server Actions / Route Handlers 전환
원칙:
- `GET` 조회 → Server Components + Prisma 직접 쿼리
- `POST/PATCH/DELETE` → Server Actions 또는 Route Handlers
- 단순 프록시(로직 없음) → `next.config.ts`의 `rewrites`로 처리

전환 우선순위:
1. 고빈도 조회: `domestic-indices`, `naver-news`, `master-quotes`, `market-voices`, `stock-terms`, `polls`
2. 인증: `auth/member`, `auth/favorites` (NextAuth 세션 + Prisma)
3. 복합 쿼리: `picks/*`, `supply-summary`

#### 2-3. 인증 통합
현재: NextAuth(소셜) + FastAPI JWT(이메일) 혼용  
목표: NextAuth Credentials Provider로 이메일 로그인 통합 → Prisma 회원 조회/검증

---

### Phase 3 — FastAPI REST 제거

**소요 시간**: 2-3주  
**범위**: Phase 2 완료 후 FastAPI에서 REST 라우터 순차 제거.

제거 대상 라우터 (스케줄러/BO 관련 제외):
- `api.py`, `auth.py` (회원 API 부분)
- `board.py`, `polls.py`, `faq.py`, `terms.py`, `popup.py`
- `finance.py`, `fsc.py`, `schedule.py`
- `stock_terms.py`, `master_quotes.py`, `market_voices.py`
- `investment_bank_news.py`, `target_price_news.py`
- `broker.py`, `ad_settings.py`

#### BO 대시보드 (유지)
`apps/scheduler/` 내 Jinja2 BO 대시보드는 내부망 전용으로 계속 운영.
Nginx Proxy Manager에서 `bo.내부도메인` → `scheduler:8001` 라우팅.

---

### Phase 4 — Docker Compose + CI/CD

**소요 시간**: 1주  
**범위**: 운영 배포 환경 구성.

#### docker-compose.prod.yml

```yaml
services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    volumes:
      - pgdata:/var/lib/postgresql/data
    env_file: .env.prod

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  web:
    build: ./apps/web
    restart: unless-stopped
    env_file: .env.prod
    depends_on: [postgres, redis]
    # Nginx Proxy Manager → web:3000

  scheduler:
    build: ./apps/scheduler
    restart: unless-stopped
    env_file: .env.prod
    depends_on: [postgres]
    # Nginx Proxy Manager → scheduler:8001 (내부망만)

volumes:
  pgdata:
```

#### .github/workflows/deploy.yml
```yaml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /opt/jurin-i
            git pull origin main
            docker compose -f docker-compose.prod.yml build web scheduler
            docker compose -f docker-compose.prod.yml up -d --no-deps web scheduler
```

---

## 완료 기준

| Phase | 검증 방법 |
|-------|----------|
| 1 | 디렉토리 이동 후 기존 기능 정상 동작 (개발 환경에서) |
| 2 | 각 API 라우트 curl/브라우저 테스트, Prisma 쿼리 결과 일치 |
| 3 | FastAPI 라우터 제거 후 동일 응답 확인, BO 대시보드 내부 접근 확인 |
| 4 | `docker compose up` 로컬 성공, GitHub Actions push → 서버 자동 배포 확인 |

---

## 변경 없는 것

- PostgreSQL 스키마 (데이터 이전 불필요)
- Python 스크리닝 알고리즘 4종
- APScheduler 작업 20개+
- FCM 푸시 알림 서비스
- 심리지수 코드 (비활성 유지)
- 프론트엔드 페이지 구조 (별도 지시 예정)
