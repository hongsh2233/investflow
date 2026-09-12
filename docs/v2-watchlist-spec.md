# 플로우(Flow) v2 관심종목 기능 기획서

**작성일**: 2026-08-26  
**상태**: 기획 확정  
**브랜치**: `dev`

---

## 현황 분석 (기존 DB)

| 항목 | 결과 |
|---|---|
| `master_quote_likes` | 주식 관심종목 ❌ — 투자 대가 **명언 좋아요** 테이블 (대가들의 한마디 탭용) |
| `master_quotes` | 주식 데이터 ❌ — 투자 대가 **명언** 테이블 |
| PER / PBR | DB에 없음. 스크리닝 결과에 `market_cap`(문자열)만 존재 |
| `naver_stock_news` | 종목 FK 없음. `keyword` 자유텍스트로만 종목 연결 |
| `investment_bank_news` | GS/MS/JPM 거시 뉴스. 종목 연결 없음 |
| 목표가 뉴스 | `target_price_news_service.py` 수집 중 (Gemini만 차단). `naver_stock_news.category`에 목표가 분류 존재 |

→ **관심종목 기능은 v2 완전 신규 설계** 필요

---

## 핵심 방향

**공신력 없는 앱의 차별화 = 정보보다 습관**

> 매일 3분: 오늘 운세 확인 → 내 종목 뉴스/목표가 체크 → 스크리닝 신호 확인

```
관심종목 탭 핵심 가치
  ✅ 즐겨찾기 종목 관련 뉴스 모아보기 (keyword 필터)
  ✅ 내 관심종목 목표가 상향/하향 알림  ← 킬러 기능
     예: "OO증권사 삼성전자 목표가 8만→9만 상향"
     (공신력 불필요 — 사실 정보 전달로 충분)
  ✅ 스크리닝 신호 발생 알림
     예: "이치모쿠 신호: 삼성전자"
  ❌ 가격 알림 (+5% 되면 알림) — 실시간 데이터 부재로 의미 없음
  ❌ IB 리포트 단독 제공 — 목표가 뉴스로 대체
```

---

## 신규 DB 테이블

```sql
CREATE TABLE stock_watchlist (
  id            SERIAL PRIMARY KEY,
  member_id     INTEGER REFERENCES members(id) ON DELETE CASCADE,
  stock_code    VARCHAR(20)  NOT NULL,   -- 종목코드 (예: 005930)
  stock_name    VARCHAR(100) NOT NULL,   -- 종목명   (예: 삼성전자)
  display_order INTEGER      DEFAULT 0,  -- 순서 변경용
  created_at    TIMESTAMP    DEFAULT now(),
  UNIQUE (member_id, stock_code)
);
```

---

## 화면 구조

### 관심종목 목록

```
┌──────────────────────────────┐
│ 관심종목              [+ 추가] │
├──────────────────────────────┤
│ ┌──────────────────────────┐ │
│ │ 삼성전자  005930         │ │
│ │ 75,400원  ▲ +2.3%       │ │  ← 빨강 (한국 주식 컨벤션: 상승=빨강)
│ └──────────────────────────┘ │
│ ┌──────────────────────────┐ │
│ │ SK하이닉스  000660       │ │
│ │ 185,000원  ▼ -1.1%      │ │  ← 파랑 (하락=파랑)
│ └──────────────────────────┘ │
│ [편집]  ← 탭하면 순서변경·삭제 │
└──────────────────────────────┘
```

### 종목 상세 (탭 → 하단 슬라이드업)

```
┌──────────────────────────────┐
│ 삼성전자 (005930)      [삭제] │
│ 75,400원  ▲ +2.3%  ▲ +1,700 │
├──────────────────────────────┤
│ 시가총액: 450조              │
│ PER/PBR: [네이버 금융에서 보기→]│  ← 초기 단순화
├──────────────────────────────┤
│ 목표가 뉴스                   │
│ · [NH] 삼성전자 목표가 9만 상향 │  ← target_price_news 필터
│ · [KB] 목표가 8.5만 유지      │
├──────────────────────────────┤
│ 관련 뉴스                     │
│ · 삼성전자 3분기 실적 발표...  │  ← keyword 매칭
│ · 삼성전자 HBM 공급 계약...   │
│   [더보기]                   │
├──────────────────────────────┤
│ 스크리닝 신호                 │
│ · 이치모쿠 구름 돌파 (오늘)   │  ← 스크리닝 결과 테이블
└──────────────────────────────┘
```

---

## 종목 추가 플로우

```
[+ 추가] 탭
  → 검색 모달 (상단 🔍 아이콘과 동일 컴포넌트)
  → 종목명 또는 코드 입력
  → 검색 결과: 종목명 + 코드 + 현재가
  → [+ 추가] 버튼
  → stock_watchlist INSERT
  → 목록 즉시 반영
```

---

## 데이터 연결 전략

### 가격 데이터

| 항목 | 방안 |
|---|---|
| 현재가 / 등락률 | 네이버 금융 API 실시간 조회 또는 스케줄러 30분 캐시 |
| 시가총액 | 스크리닝 결과 테이블의 `market_cap` 재활용 |
| PER / PBR | 초기: 네이버 금융 외부링크 → 추후 스크래핑 추가 |

### 뉴스·목표가 연결

```python
# 목표가 뉴스: naver_stock_news category 필터 + 종목명 매칭
target_news = db.query(NaverStockNews).filter(
    NaverStockNews.keyword == stock_name,
    NaverStockNews.category.in_(["목표가", "수주", "실적발표"])
).order_by(NaverStockNews.pub_datetime.desc()).limit(3)

# 일반 뉴스: keyword 또는 title LIKE 매칭
news = db.query(NaverStockNews).filter(
    (NaverStockNews.keyword == stock_name) |
    (NaverStockNews.title.contains(stock_name))
).order_by(NaverStockNews.pub_datetime.desc()).limit(5)

# 스크리닝 신호: 각 스크리닝 결과 테이블에서 stock_name 검색
screening = db.query(IchiMokuResult).filter(
    IchiMokuResult.stock_name == stock_name,
    IchiMokuResult.created_at >= today
).first()
```

---

## 앱 전체 콘텐츠 전략

| 루틴 | 탭 | 콘텐츠 | 방문 이유 |
|---|---|---|---|
| 아침 출근 | 투자운세 | 오늘의 띠/별자리/MBTI 운세 | 매일 바뀜, 나만의 운세 |
| 장중 체크 | 관심종목 | 내 종목 뉴스 + 목표가 변경 | "내 종목 무슨 일 있나?" |
| 수시 알림 | 관심종목 | 스크리닝 신호 발생 | "신호 뜬 종목 확인" |
| 여가 | 대가들의 한마디 | 투자 대가 명언 | 짧고 인상적, 공유하고 싶음 |

### 바이럴 포인트

| 콘텐츠 | 공유 형태 |
|---|---|
| MBTI 투자성향 결과 | "나는 INTJ → 찰리 멍거 스타일!" 이미지 카드 |
| 오늘의 운세 | "용띠 오늘 ★★★★☆ — 분할 매수 유효" 공유 |
| 대가 명언 | 텍스트 카드 이미지 (카카오 / 인스타) |

---

## 구현 우선순위

```
Phase 1: 기본 CRUD
  ├── stock_watchlist 테이블 생성 (SQLAlchemy migration)
  ├── 관심종목 목록 조회 / 추가 / 삭제 API
  └── 순서 변경 (편집 모드)

Phase 2: 가격 연동
  ├── 현재가/등락 조회 API (네이버 금융)
  └── 종목 검색 API (종목명/코드)

Phase 3: 뉴스·목표가 연결
  ├── 목표가 뉴스 keyword 필터
  ├── 일반 뉴스 keyword/title 매칭
  └── 스크리닝 신호 연결

Phase 4: 고도화 (선택)
  ├── PER/PBR 네이버 금융 스크래핑
  └── 푸시 알림 (목표가 변경 / 스크리닝 신호)
```

---

## 미결 사항

- [ ] 가격 데이터: 실시간 API 호출 vs 스케줄러 30분 캐시
- [ ] 비로그인 사용자 관심종목: localStorage 임시 저장 여부
- [ ] 종목 검색 DB: 전체 상장 종목 코드 테이블 구축 방법 (현재 없음)
- [ ] 스크리닝 신호 알림: 푸시 알림 vs 앱 내 배지
- [ ] 목표가 뉴스 파싱: 현재 `target_price_news_service.py`가 수집하는 데이터 구조 확인 필요
