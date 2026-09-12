# Gemini 제거 & 재활성화 마이그레이션 가이드

**상태**: 🔴 완료 (1차: 2026-07-08 / 2차 전면 차단: 2026-08-03)  
**목적**: 비용 절감 (월 $120-140 추정)  
**재활성화**: AI 구독 수익 모델 확립 후 선별 재활성화 예정  
**아카이브 위치**: `archive/gemini-services/` (C안 마이그레이션 시 이동 예정)

---

## 📋 제거된 기능 목록

### [2026-08-03 추가 차단] 헬퍼 함수 레벨 전면 차단 (10건)

기존 1차 제거(2026-07-08)는 주요 함수(generate_*)를 주석처리했으나, 헬퍼 함수 레벨에서 여전히 Gemini를 호출하는 코드가 남아 있어 실제 청구가 발생. 2026-08-03에 조기 `return None/""` 추가로 완전 차단.

| 파일 | 함수 | 차단 패턴 |
|------|------|----------|
| `services/target_price_news_service.py` | `_process_with_gemini()` | `return None` |
| `services/sentiment_analysis_service.py` | `_call_gemini_sentiment()` | `return None` |
| `services/market_voice_service.py` | `_summarize_with_gemini()` | `return None` |
| `services/investment_bank_news_service.py` | `_translate_with_gemini()` | `return None` |
| `services/daily_fortune_gemini_service.py` | `_call_gemini()` | `return ""` |
| `services/daily_issue_gemini_service.py` | `_call_gemini()` | `return None` |
| `services/supply_summary_gemini_service.py` | `_call_gemini()` | `return None` |
| `services/market_closing_gemini_service.py` | `_call_gemini()` | `return None` |
| `app/api/mbti-investment-advice/route.ts` | `POST` 핸들러 | 503 응답 |
| `app/api/jubti-strategy/route.ts` | `POST` 핸들러 | 503 응답 |

마커: `# [2026-08-03 Gemini 제거] 비용 절감 — 모든 Gemini 호출 차단`

---

### [2026-07-08 1차 제거] 주요 함수 주석처리 (5건)

### 1. 오늘의 띠/별자리 운세 생성 (Daily Fortune)

**파일**: `/apps/admin/app/services/daily_fortune_gemini_service.py`  
**함수**: `generate_daily_fortunes(target_date: Optional[date] = None) -> dict`  
**상태**: ✅ 주석처리 완료 (라인 135-186)  
**마커**: `# [2026-07-08 Gemini 제거]`  
**비용 절감**: $5/월

**재활성화 단계**:
```python
1. 함수 주석 해제 (라인 135-186)
2. scheduler_service.py의 DailyFortuneScheduler._generate() 복원
   - Line 2026-2028: generate_daily_fortunes 호출 복원
   - Line 2031: print 로그 메시지 복원
3. 스케줄러 시작 검증 (APScheduler 확인)
4. 테스트: `/api/fortune?type=animal&key=쥐` 등 호출 확인
```

---

### 2. 장마감 시황 AI 생성 (Market Closing Summary)

**파일**: `/apps/admin/app/services/market_closing_gemini_service.py`  
**함수**: `generate_and_post_closing_summary(db: Session, target_date: date) -> bool`  
**상태**: ✅ 주석처리 완료 (라인 577-671)  
**마커**: `# [2026-07-08 Gemini 제거]`  
**비용 절감**: $80-100/월 (가장 높음)

**재활성화 단계**:
```python
1. 함수 주석 해제 (라인 577-671)
2. scheduler_service.py의 collect_market_closing_summary() 내 호출 복원
   - Line 789-794: 함수 호출 및 로그 복원
3. 스케줄 확인: 매일 16:25 KST (게시판 B001에 auto-posting)
4. 테스트:
   - 마감 시황이 B001 게시판에 pending 상태로 등록되는지 확인
   - AI 요약 내용 정상 생성 확인
```

---

### 3. 수급 동향 AI 요약 (Supply Summary)

**파일**: `/apps/admin/app/services/supply_summary_gemini_service.py`  
**함수**: `generate_and_save_supply_summary(db: Session, bizdate: str, collected_time: str) -> int`  
**상태**: ✅ 주석처리 완료 (라인 261-313)  
**마커**: `# [2026-07-08 Gemini 제거]`  
**비용 절감**: $20/월

**재활성화 단계**:
```python
1. 함수 주석 해제 (라인 261-313)
2. scheduler_service.py의 collect_naver_supply_data() 내 호출 복원
   - Line 1058: import 복원
   - Line 1080-1087: 함수 호출 및 에러 처리 복원
3. 스케줄 확인: 08:40~15:40 30분 간격, 16:40~20:40 1시간 간격
4. 테스트:
   - supply_summary_ai_summaries 테이블에 AI 요약 저장 확인
   - 프론트엔드 수급 카드의 AI 요약 표시 확인
```

---

### 4. 금일 이슈 AI 요약 (Daily Issue Summary)

**파일**: `/apps/admin/app/services/daily_issue_gemini_service.py`  
**함수**: `generate_and_save_daily_issue_summary(db: Session, target_date: date) -> bool`  
**상태**: ✅ 주석처리 완료 (라인 83-121)  
**마커**: `# [2026-07-08 Gemini 제거]`  
**비용 절감**: $10/월

**재활성화 단계**:
```python
1. 함수 주석 해제 (라인 83-121)
2. scheduler_service.py의 collect_naver_stock_news() 내 호출 복원
   - Line 1292: import 복원
   - Line 1294-1302: 함수 호출 및 에러 처리 복원
3. 스케줄 확인: 평일 08:30, 12:30, 19:30
4. 테스트:
   - daily_issue_summaries 테이블에 이슈 요약 저장 확인
   - 마감 시황 및 관리자 페이지에서 이슈 정보 표시 확인
```

---

### 5. 게시글 내용 AI 요약 (Post Content Summary)

**파일**: `/apps/admin/app/routers/api.py`  
**함수**: `_summarize_content_with_gemini(content: str) -> Optional[str]`  
**상태**: ✅ 주석처리 완료 (라인 92-114)  
**호출처**: Line 1108 (방명록/게시글 등록 시)  
**마커**: `# [2026-07-08 Gemini 제거]`  
**비용 절감**: $5/월 (선택적 기능)

**재활성화 단계**:
```python
1. 함수 주석 해제 (라인 92-114)
2. API 엔드포인트 호출 복원 (라인 1107-1110)
3. 프론트엔드: use_ai_summary=true 파라미터 활성화
4. 테스트: CreatePostRequest에 use_ai_summary=true로 요청 → 요약 생성 확인
```

---

### 6. 프론트엔드 AI 요약 UI 비활성화

**파일들**:
- `/apps/web_new/app/components/module/home/SupplySummaryCard.tsx` (라인 93-99)
- `/apps/web_new/app/api/supply-summary/route.ts` (라인 244-310)

**상태**: ✅ 주석처리 완료  
**마커**: `// [2026-07-08 Gemini 제거]`

**재활성화 단계**:
```typescript
1. SupplySummaryCard.tsx:
   - Line 94: const sharedSummary 라인 주석 해제
   - Line 99: AI 요약 표시 JSX 주석 해제

2. supply-summary/route.ts:
   - Line 244-310: AI 요약 조회 로직 전체 주석 해제
   - kospiSummary, kosdaqSummary 초기화 부분 원래대로 복원

3. 테스트: 수급 카드의 AI 요약 텍스트 표시 확인
```

---

## 🔄 전체 재활성화 체크리스트 (Phase 2-3)

- [ ] **데이터 모델 검증**: daily_fortunes, supply_summary_ai_summaries, daily_issue_summaries 테이블 상태 확인
- [ ] **GEMINI_API_KEY 환경변수**: 값이 설정되어 있고 유효한지 확인
- [ ] **Gemini 서비스 함수 재활성화**: 위의 5개 함수 모두 주석 해제
- [ ] **스케줄러 태스크 복원**: scheduler_service.py의 모든 import 및 호출 복원
- [ ] **API 엔드포인트 테스트**:
  - `GET /api/fortunes` → 운세 데이터 반환
  - `POST /api/boards/{board_id}/posts?use_ai_summary=true` → 요약 생성
  - `GET /api/supply-summary` → AI 요약 포함
- [ ] **UI 구성요소 테스트**:
  - 수급 카드에서 AI 요약 텍스트 표시
  - 마감 시황 게시글에 AI 콘텐츠 포함
- [ ] **프로덕션 배포**: 스테이징에서 1-2일 모니터링 후 배포

---

## 💰 예상 비용 절감 요약

| 기능 | 호출/월 | 비용/월 | 상태 |
|------|---------|---------|------|
| 오늘의 운세 | 30회 | $5 | 🔴 제거 |
| 장마감 시황 | 20회 | $80-100 | 🔴 제거 |
| 수급 요약 | 300회 | $20 | 🔴 제거 |
| 금일 이슈 | 60회 | $10 | 🔴 제거 |
| 게시글 요약 | 50회 | $5 | 🔴 제거 |
| **합계** | | **$120-140** | |

---

## ⚠️ 주의사항

1. **코드 보존**: 완전 삭제 ❌ → 주석처리만 (재활성화 용이)
2. **DB 데이터 보존**: 기존 AI 요약 데이터는 유지됨 (history 목적)
3. **모델 버전 확인**: Gemini 모델 버전이 변경되었을 수 있음
   - 현재: `gemini-2.5-flash`
   - Phase 2에서 최신 모델 확인 후 업데이트
4. **API 응답 구조 검증**: 재활성화 시 Gemini 응답 포맷 재검증 필요
5. **테스트 커버리지**: 각 기능별 통합 테스트 추가 권장

---

## 📞 Support & Contacts

문제 발생 시:
1. 해당 마이그레이션 섹션의 "재활성화 단계" 체크리스트 확인
2. 스케줄러 로그 확인 (`/admin/logs` 또는 서버 로그)
3. Gemini API 할당량 및 에러 메시지 확인

---

**작성**: 2026-07-08  
**검토**: Phase 2 시작 전 (2026년 9월 말 예정)
