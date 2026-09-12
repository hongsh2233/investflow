# Jurin-i "투자 놀이터" 리디자인 계획서 (v2.0)

**프로젝트명**: Jurin-i 투자 놀이터 전환  
**작성일**: 2026-07-14  
**상태**: 계획 확정 (구현 대기)  
**참고**: 경로 표기는 C안 마이그레이션 전 기준. 이전 후 `apps/admin/` → `apps/scheduler/`, `apps/web_new/` → `apps/web/`

---

## Context

Jurin-i는 현재 "투자 정보 플랫폼"으로 포지셔닝되어 있다. 홈 페이지 상위 5개 모듈이 모두 데이터/지표(심리지수→수급→시장지수→투자자동향→뉴스) 중심이고, 엔터테인먼트 요소(주BTI, 운세)는 최하단에 묻혀 있어 스크롤하지 않으면 보이지 않는다.

**목표**: 개인 투자자와 예비 투자자를 위한 "투자 놀이터"로 전환한다.
- 주BTI/운세 등을 유료화 대비 맛보기로 제공
- 뉴스, 투자 팁, 대가들의 한마디를 유지·부각
- 주식 용어 퀴즈, 일일 미션 등 새로운 놀이 요소 추가
- 수익 모델: 포인트 소진 + 월 구독 혼합

---

## 1. 홈 페이지 리디자인 (놀이터 통합)

현재 5탭(홈/검색/뉴스시황/추천/설정) 구조를 유지하되, **홈 페이지 자체를 놀이터 중심으로 재배치**한다.

### 현재 홈 모듈 순서
```
1. SentimentIndexCard        (공포/탐욕 게이지)
2. SupplySummaryCard         (수급 요약)
3. MarketTabSection          (시장 지수/환율)
4. [AdZone B1]
5. InvestorTrendChart        (투자자 동향)
6. MainCardNews              (주요 뉴스)
7. HomeMarketCta             (AI 추천 CTA)
8. FavoriteStocks            (관심종목, 로그인 필요)
9. RealtimeSearchSection     (실시간 검색, 로그인 필요)
10. [AdZone B2]
11. StockTermBox             (주식 용어)
12. JubtiSection             (주BTI 퀴즈)
13. FortuneSection           (오늘의 운세)
14. [배너]
15. RandomAffiliateCard      (제휴 상품)
```

### 신규 홈 모듈 순서
```
1. [신규] DailyMissionBar    ← 오늘의 미션 진행률 (3/5 완료!)
2. RandomMasterQuote         ← 대가들의 한마디 (기존 stock-chat에만 있던 것을 홈 상단으로)
3. SentimentIndexCard        ← 공포/탐욕 게이지 (짧고 임팩트)
4. [신규] QuickPlayButtons   ← 놀이 바로가기 (용어퀴즈 / 주BTI / 운세 / 오늘의 투표)
5. MainCardNews              ← 주요 뉴스 3건
6. MarketTabSection          ← 시장 지수/환율 (축소 가능)
7. StockTermBox              ← 용어 퀴즈 형태로 리디자인
8. [AdZone]
9. HomeMarketCta             ← AI 추천 CTA
10. FavoriteStocks           ← 관심종목
11. [배너/제휴]
```

### 홈에서 제거/이동
| 컴포넌트 | 이동 위치 | 이유 |
|---------|---------|------|
| JubtiSection | QuickPlayButtons → `/jubti` 전용 페이지 | 홈 경량화, 전용 페이지에서 더 풍부한 UX |
| FortuneSection | QuickPlayButtons → `/fortune` 전용 페이지 | 홈 경량화, 맛보기/프리미엄 분리에 유리 |
| SupplySummaryCard | 뉴스/시황(briefing) 탭으로 이동 | 전문 투자자 위주, 놀이터 톤에 맞지 않음 |
| InvestorTrendChart | 뉴스/시황 탭으로 이동 | 전문 투자자 위주 |
| RealtimeSearchSection | 검색(Header) 기능으로 통합 | 홈 공간 확보 |

### 주요 변경 파일
- `apps/web_new/app/page.tsx` — 모듈 순서 재배치
- `apps/web_new/app/components/module/home/` — 새 컴포넌트 추가
- `apps/web_new/app/components/module/random-master-quote.tsx` — 홈 import 추가 (기존 컴포넌트 재활용)

---

## 2. 신규 기능: 주식 용어 퀴즈

기존 `StockTerm` 데이터(500+개)를 활용한 4지선다 퀴즈 게임.

### 게임 규칙
- 10문제 1세트, 문항당 15초 시간제한
- 점수 = 정답 수 × 남은 시간 보너스
- 일간/주간 리더보드
- 포인트: 7+정답 → +20P, 만점 → +50P

### 백엔드 구현
- **새 DB 모델** (`apps/admin/app/engine/models.py`):
  ```python
  class QuizSession(Base):
      __tablename__ = "quiz_sessions"
      id = Column(Integer, primary_key=True)
      member_id = Column(Integer, ForeignKey("members.id"))
      score = Column(Integer, default=0)
      correct_count = Column(Integer, default=0)
      total_count = Column(Integer, default=10)
      duration_seconds = Column(Integer)
      created_at = Column(DateTime, default=func.now())
  ```
- **새 API** (별도 router 또는 `api.py`에 추가):
  - `GET /api/quiz/questions` — 랜덤 10문제 + 오답 보기 3개 생성
  - `POST /api/quiz/submit` — 결과 제출, 포인트 지급
  - `GET /api/quiz/leaderboard` — 일간/주간 랭킹
  - `GET /api/quiz/my-history` — 내 퀴즈 기록

### 프론트엔드 구현
- `apps/web_new/app/quiz/page.tsx` — 퀴즈 전용 페이지
- `apps/web_new/app/components/module/home/StockTermBox.tsx` — "퀴즈 도전하기" CTA 버튼 추가
- 타이머 + 진행바 + 결과 화면 + 리더보드 UI

### 기존 코드 재활용
| 기존 코드 | 활용 방식 |
|----------|---------|
| `apps/admin/app/routers/stock_terms.py` | StockTerm 모델, `GET /api/stock-terms` API |
| `apps/web_new/app/components/module/home/stock-term-box.tsx` | 현재 랜덤 용어 표시 로직 |
| `apps/admin/app/services/member_point_service.py` | 포인트 지급 (새 reason 코드 추가) |

---

## 3. 신규 기능: 일일 미션 시스템

매일 3~5개 미니 미션을 완료하면 포인트 획득. 앱 내 기존 행동을 미션으로 추적.

### 미션 목록
| 미션 | 조건 | 보상 |
|------|------|------|
| 오늘의 용어 학습 | StockTermBox 열람 | +10P |
| 뉴스 3개 읽기 | 뉴스 카드 클릭 3회 | +10P |
| 대가 명언 좋아요 | MasterQuoteLike 1회 | +10P |
| 주식 용어 퀴즈 참여 | QuizSession 완료 1회 | +15P |
| 투표 참여 | PollVote 1회 | +10P |
| **전체 완료 보너스** | 모든 미션 클리어 | +50P |

### 백엔드 구현
- **새 DB 모델** (`apps/admin/app/engine/models.py`):
  ```python
  class DailyMissionTemplate(Base):
      __tablename__ = "daily_mission_templates"
      id = Column(Integer, primary_key=True)
      mission_type = Column(String(50))          # stock_term, news_read, quote_like, quiz, poll_vote
      description = Column(String(200))
      point_reward = Column(Integer, default=10)
      condition_type = Column(String(50))         # count, boolean
      condition_value = Column(Integer, default=1)
      is_active = Column(Boolean, default=True)
      order_index = Column(Integer, default=0)

  class MemberDailyMission(Base):
      __tablename__ = "member_daily_missions"
      id = Column(Integer, primary_key=True)
      member_id = Column(Integer, ForeignKey("members.id"))
      mission_date = Column(Date)
      mission_template_id = Column(Integer, ForeignKey("daily_mission_templates.id"))
      progress = Column(Integer, default=0)        # 현재 진행 수 (예: 뉴스 2/3개)
      is_completed = Column(Boolean, default=False)
      completed_at = Column(DateTime, nullable=True)
  ```
- **새 API**:
  - `GET /api/missions/today` — 오늘의 미션 목록 + 진행 상태
  - `POST /api/missions/{mission_id}/progress` — 미션 진행 업데이트 + 완료 시 포인트 지급
  - `GET /api/missions/history` — 미션 완료 히스토리

### 프론트엔드 구현
- `apps/web_new/app/components/module/home/DailyMissionBar.tsx` — 홈 상단 미션 진행률 바
- 각 기존 컴포넌트에 미션 완료 콜백 추가 (뉴스 클릭, 좋아요, 퀴즈 완료 시)

### 기존 코드 재활용
| 기존 코드 | 활용 방식 |
|----------|---------|
| `member_point_service.py` | 포인트 지급 (새 reason 코드) |
| `Poll`/`PollVote` 모델 | 투표 미션 추적 |
| `MasterQuoteLike` 모델 | 좋아요 미션 추적 |

---

## 4. 운세/주BTI 맛보기 + 프리미엄 구조

### 3단계 접근

| 등급 | 운세 | 주BTI | AI 조언 |
|------|------|-------|---------|
| **비로그인** | 첫 1문장만, 나머지 블러 | 퀴즈 가능, 결과는 유형명만 | 잠금 |
| **무료 회원** | 전체 본문 + 투자 팁 | 전체 결과 + 대가 매칭 | 잠금 |
| **프리미엄** (구독/포인트) | 전체 + AI 투자 종합 조언 | 전체 + AI 맞춤 전략 | 해금 |

### 구현
- `FortuneSection.tsx`: 비로그인 시 `fortune_text` 첫 문장만 표시 + 블러 오버레이 + "회원가입하고 전체 보기" CTA
- `JubtiSection.tsx`: 비로그인 시 결과 유형명/캐릭터만, "추천 투자 개념"은 블러
- AI 기능: Gemini 선별 재활성화 (프리미엄 사용자 요청 시만 호출)
  - `/api/mbti-investment-advice` — 포인트 50P 또는 구독자 무료
  - `/api/jubti-strategy` — 포인트 50P 또는 구독자 무료

### Gemini 비용 관리
| 기능 | 재활성화 여부 | 비용 | 조건 |
|------|-------------|------|------|
| 운세 본문 생성 | ✅ 재활성화 | ~$5/월 (24 call/일) | 배치 생성 |
| AI 투자 조언 | ✅ 재활성화 | pay-per-use | 프리미엄 사용자만 |
| AI 주BTI 전략 | ✅ 재활성화 | pay-per-use | 프리미엄 사용자만 |
| 수급 AI 요약 | ❌ 비활성 유지 | - | - |
| 시황 AI 요약 | ❌ 비활성 유지 | - | - |
| 이슈 AI 요약 | ❌ 비활성 유지 | - | - |

---

## 5. 수익 모델: 포인트 + 구독 혼합

### 포인트 체계 확장

**신규 적립 항목** (`member_point_service.py`):
```
용어 퀴즈 7+정답:  +20P  (reason: quiz_pass)
용어 퀴즈 만점:    +50P  (reason: quiz_perfect)
일일 미션 개별:    +10~15P (reason: mission_complete)
일일 미션 전체:    +50P  (reason: mission_all_complete)
투표 참여:         +10P  (reason: poll_vote)
연속 로그인 7일:   +100P (reason: login_streak_7)
연속 로그인 30일:  +500P (reason: login_streak_30)
```

**기존 적립 항목** (유지):
```
가입 보너스:   +100P  (signup_bonus)
일일 로그인:   +20P   (daily_login)
주BTI 최초:   +50P   (jubti_first)
MBTI 최초:    +50P   (mbti_first)
띠 최초:      +30P   (zodiac_animal_first)
별자리 최초:   +30P   (zodiac_sign_first)
게시글 좋아요: +20P   (post_like)
VIP 환영:     +4900P (vip_welcome)
```

**신규 소비 항목**:
```
AI 투자 종합 조언:  -50P  (reason: ai_investment_advice)
AI 주BTI 전략:     -50P  (reason: ai_jubti_strategy)
```

### 구독 모델 (Phase 4 이후)
- 프리미엄 월 구독: ₩4,900/월
- 구독자 혜택: AI 기능 무제한 + 스크리닝 전체 공개 + 광고 제거
- `Member` 모델에 `subscription_type`, `subscription_expires_at` 필드 추가
- 결제 연동: Toss Payments 또는 인앱결제 (Capacitor)

### 레벨 시스템 (포인트 누적 기반)
```
Lv.1 주린이        (0P~)
Lv.2 새내기 투자자  (500P~)
Lv.3 중급 투자자    (2,000P~)
Lv.4 숙련 투자자    (5,000P~)
Lv.5 투자 달인      (10,000P~)
Lv.6 투자 마스터    (20,000P~)
```
- `Member.point_balance` 누적값 기반 실시간 계산
- 설정(마이) 페이지에 레벨 진행 바 표시

---

## 6. 뉴스/대가 명언 부각

### 대가들의 한마디
- **홈 상단 배치**: `RandomMasterQuote` 컴포넌트를 홈 2번째 모듈로 이동
  - 현재: `stock-chat/page.tsx`에서만 사용
  - 변경: `page.tsx` (홈)에도 import
- 기존 컴포넌트 그대로 재활용 (`app/components/module/random-master-quote.tsx`)
- JuBTI 유형별 가중치 매칭 유지 (`jubtiMasters.ts`의 `pickWeightedByMaster`)

### 뉴스 유지
- `MainCardNews` 홈 5번째 위치 유지
- 뉴스/시황(briefing) 탭에 수급 요약, 투자자 동향을 통합하여 정보 밀도 유지

### 투자 팁
- 현재: 운세의 `investment_tip` 필드로 제공
- 향후: 별도 "오늘의 투자 팁" 위젯으로 분리 가능

---

## 7. 구현 우선순위

### Phase 1 (1~2주): 홈 재배치 + 톤 전환
기존 코드만 재배치하는 작업. 새 코드 최소화.

| # | 작업 | 파일 |
|---|------|------|
| 1 | 홈 모듈 순서 변경 | `page.tsx` |
| 2 | RandomMasterQuote 홈 상단 이동 | `page.tsx`, `random-master-quote.tsx` |
| 3 | JubtiSection → `/jubti` 전용 페이지 분리 | `app/jubti/page.tsx` (신규) |
| 4 | FortuneSection → `/fortune` 전용 페이지 분리 | `app/fortune/page.tsx` (신규) |
| 5 | QuickPlayButtons 컴포넌트 생성 | `components/module/home/QuickPlayButtons.tsx` |
| 6 | 헤더 슬로건/톤 변경 | `config/nav-items.json` |
| 7 | SupplySummaryCard, InvestorTrendChart → briefing 탭 이동 | `briefing/page.tsx` |

### Phase 2 (2~4주): 주식 용어 퀴즈
| # | 작업 | 파일 |
|---|------|------|
| 8 | QuizSession DB 모델 + 마이그레이션 | `models.py`, 마이그레이션 파일 |
| 9 | 퀴즈 API (문제 생성, 제출, 리더보드) | `routers/` 또는 `api.py` |
| 10 | 퀴즈 페이지 UI | `app/quiz/page.tsx` |
| 11 | StockTermBox에 "퀴즈 도전" CTA 추가 | `stock-term-box.tsx` |
| 12 | 포인트 연동 | `member_point_service.py` |

### Phase 3 (3~5주): 일일 미션 시스템
| # | 작업 | 파일 |
|---|------|------|
| 13 | DailyMissionTemplate, MemberDailyMission DB 모델 | `models.py` |
| 14 | 미션 API (오늘의 미션, 완료 처리) | `routers/` 또는 `api.py` |
| 15 | DailyMissionBar 홈 컴포넌트 | `DailyMissionBar.tsx` |
| 16 | 기존 행동에 미션 완료 콜백 연결 | 뉴스, 좋아요, 퀴즈 컴포넌트들 |
| 17 | 연속 로그인 보너스 로직 | `member_point_service.py` |

### Phase 4 (5~8주): 프리미엄 + AI 재활성화
| # | 작업 | 파일 |
|---|------|------|
| 18 | 운세/주BTI 맛보기 블러 처리 | `FortuneSection.tsx`, `JubtiSection.tsx` |
| 19 | Gemini AI 선별 재활성화 | `daily_fortune_gemini_service.py`, `scheduler_service.py` |
| 20 | AI 기능 포인트 소비 연동 | `member_point_service.py`, API routes |
| 21 | 구독 모델 DB 준비 | `models.py`, 마이그레이션 |
| 22 | 레벨 시스템 UI | 설정 페이지 |

---

## 8. 검증 방법

### Phase 1 검증
- [ ] 홈 페이지 로드 → 모듈 순서: 미션바 → 대가명언 → 심리지수 → 바로가기 → 뉴스
- [ ] QuickPlayButtons → 용어퀴즈, 주BTI, 운세, 투표 각 버튼 클릭 시 정상 이동
- [ ] `/jubti`, `/fortune` 페이지 정상 접근 확인
- [ ] briefing 탭에서 수급 요약, 투자자 동향 정상 표시
- [ ] 기존 5탭 네비게이션 정상 동작

### Phase 2 검증
- [ ] `GET /api/quiz/questions` → 10문제 + 각 4개 보기(정답 1 + 오답 3) 반환
- [ ] 퀴즈 완료 → `QuizSession` DB 저장 확인
- [ ] 7+정답 시 +20P, 만점 시 +50P 포인트 지급 확인
- [ ] 리더보드 정렬 정확성 (점수 내림차순, 동점 시 시간순)

### Phase 3 검증
- [ ] `GET /api/missions/today` → 오늘의 미션 3~5개 반환
- [ ] 뉴스 3개 클릭 후 미션 자동 완료 → 포인트 지급 확인
- [ ] 전체 미션 완료 시 보너스 +50P 지급 확인
- [ ] DailyMissionBar에 실시간 진행률 반영 (3/5 → 4/5 → 5/5 완료!)

### Phase 4 검증
- [ ] 비로그인 사용자: 운세 첫 문장만 표시, 나머지 블러
- [ ] 무료 회원: 운세 전체 + 투자 팁 표시
- [ ] 프리미엄 사용자: AI 조언 요청 → Gemini 스트리밍 응답 정상
- [ ] 포인트 50P 차감 확인 (잔액 부족 시 에러 메시지)

---

## 향후 고려 (Phase 5+)

- **일일 예측 게임**: KOSPI/종목 종가 예측 → 적중 시 포인트 + 리더보드
- **모의 투자 (Paper Trading)**: 가상 1000만원 매매 시뮬레이션 (개발 공수 가장 큼)
- **소셜 기능**: 퀴즈/예측 결과 공유, 친구 초대
- **커뮤니티 탭**: 주톡(stock-chat) + 게시판 + 투표 통합

---

## 관련 문서

| 문서 | 경로 |
|------|------|
| Gemini 제거 마이그레이션 가이드 | `/docs/gemini-removal-migration-guide.md` |
| 부하 최적화 로그 | `/docs/load-optimization-log.md` |
| 기존 리디자인 계획 (v1, 아키텍처) | `/root/.claude/plans/adr-adr-polymorphic-blossom.md` |

---

**작성**: 2026-07-14  
**다음 리뷰**: Phase 1 착수 전
