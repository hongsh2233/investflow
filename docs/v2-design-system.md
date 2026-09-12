# 플로우(Flow) v2 디자인 시스템

**작성일**: 2026-08-26  
**상태**: 제안

---

## 브랜드 컨셉

**"Midnight Flow"** — 고요한 확신 + 흐르는 기회

- 밤 시장의 흐름을 읽는 전문적 깊이감
- 투자운세 탭의 신비감 + 금융 앱의 신뢰감을 동시에
- 밤하늘 인디고 배경 위에 흐르는 금빛 포인트

---

## 컬러 팔레트

### Primary — Midnight Indigo

| 이름 | HEX | 용도 |
|---|---|---|
| Background | `#0E0E2A` | 메인 배경 (다크 모드) |
| Surface | `#1A1A3E` | 카드·모달·서피스 |
| Surface Elevated | `#2D2D6B` | 헤더·섹션 구분선 |

### Accent — Flow Amber (금빛 흐름)

| 이름 | HEX | 용도 |
|---|---|---|
| Primary | `#F59E0B` | 주요 CTA 버튼, 포인트 아이콘 |
| Light | `#FCD34D` | 하이라이트, 강조 텍스트 |
| Dark | `#D97706` | 호버·선택 상태 |

### 한국 주식 컨벤션 (필수)

| 이름 | HEX | 용도 |
|---|---|---|
| Bull (상승) | `#EF4444` | 가격 상승, 양봉 |
| Bear (하락) | `#3B82F6` | 가격 하락, 음봉 |

> ⚠️ 한국 주식앱 표준: 빨강=상승, 파랑=하락 (국제 관례와 반대)

### 보조색

| 이름 | HEX | 용도 |
|---|---|---|
| Success | `#10B981` | 완료, 저장, 알림 확인 |
| Warning | `#F59E0B` | 주의 (Accent와 공유) |
| Error | `#EF4444` | 오류 (Bull과 공유) |
| Neutral 600 | `#6B7280` | 보조 텍스트, 아이콘 |
| Neutral 400 | `#9CA3AF` | Placeholder, 비활성 |

---

## 다크 / 라이트 모드 토큰

**기본값: 다크 모드** (투자 앱 특성 + 운세 탭 분위기)

| 토큰 | 다크 | 라이트 |
|---|---|---|
| `--color-bg` | `#0E0E2A` | `#F8F7FF` |
| `--color-surface` | `#1A1A3E` | `#FFFFFF` |
| `--color-surface-elevated` | `#2D2D6B` | `#F3F4F6` |
| `--color-text-primary` | `#F9FAFB` | `#111827` |
| `--color-text-secondary` | `#9CA3AF` | `#6B7280` |
| `--color-accent` | `#F59E0B` | `#D97706` |
| `--color-border` | `#374151` | `#E5E7EB` |

---

## 타이포그래피

| 역할 | 폰트 | 비고 |
|---|---|---|
| 한국어 전체 | Pretendard | 웹폰트, 가독성 최고 |
| 숫자·코드 | Roboto Mono | 가격, 주식 코드 |
| 영문 보조 | Inter | 시스템 폰트 fallback |

```css
font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
```

### 폰트 사이즈 스케일

| 이름 | px | 용도 |
|---|---|---|
| `text-xs` | 12px | 태그, 캡션 |
| `text-sm` | 14px | 보조 텍스트 |
| `text-base` | 16px | 본문 |
| `text-lg` | 18px | 카드 제목 |
| `text-xl` | 20px | 섹션 제목 |
| `text-2xl` | 24px | 페이지 제목 |
| `text-3xl` | 30px | 운세 숫자, 주요 수치 |

---

## 탭별 분위기

### 투자운세 (`/fortune`)
- 배경: Midnight Indigo `#0E0E2A`
- 운세 카드: Surface `#1A1A3E` + 골드 테두리 `#F59E0B`
- 별·아이콘: Amber `#FCD34D`
- 텍스트: 부드러운 흰색 `#F9FAFB`

### 뉴스 (`/news`)
- 배경: 중립 (라이트 모드 기본 권장)
- 상승/하락 태그: 빨강 `#EF4444` / 파랑 `#3B82F6`
- 뉴스 카드: 흰 배경 + 연한 테두리

### 관심종목 (`/watchlist`)
- 가격 숫자: Roboto Mono
- 상승 `+3.2%` → `#EF4444` 빨강
- 하락 `-1.8%` → `#3B82F6` 파랑
- 0% → `#9CA3AF` 중립

### 대가들의 한마디 (`/masters`)
- 배경: Surface Elevated `#2D2D6B`
- 인용부호: 대형 골드 `"` `#F59E0B` opacity 30%
- 이름: Amber `#F59E0B`
- 명언 텍스트: 흰색, 중간 굵기

---

## 컴포넌트 가이드

### 버튼

```
Primary (CTA)  : bg #F59E0B, text #0E0E2A, bold
Secondary      : border #F59E0B, text #F59E0B, transparent bg
Ghost          : text #9CA3AF, no border
Danger         : bg #EF4444, text white
```

### 카드

```
기본 카드    : bg #1A1A3E, border #374151, radius 12px
운세 카드    : bg #1A1A3E, border-left 3px solid #F59E0B
뉴스 카드   : bg white, shadow, radius 8px
픽 카드      : bg #1A1A3E, 상단 그레이드 색상 바
```

### 바텀 탭

```
활성 탭     : 아이콘 + 라벨 #F59E0B, 상단 인디케이터 선
비활성 탭   : 아이콘 + 라벨 #6B7280
배경        : #1A1A3E, 상단 border 1px #374151
```

---

## Tailwind 설정 예시

```ts
// tailwind.config.ts
theme: {
  extend: {
    colors: {
      flow: {
        bg:       '#0E0E2A',
        surface:  '#1A1A3E',
        elevated: '#2D2D6B',
        amber:    '#F59E0B',
        gold:     '#FCD34D',
        bull:     '#EF4444',
        bear:     '#3B82F6',
      }
    },
    fontFamily: {
      sans: ['Pretendard', 'system-ui', 'sans-serif'],
      mono: ['Roboto Mono', 'monospace'],
    }
  }
}
```

---

## 미결 사항

- [ ] 라이트 모드 기본으로 할지, 다크 모드 기본으로 할지 최종 결정
- [ ] 앱 아이콘 / 스플래시 스크린 디자인 방향
- [ ] 운세 탭 배경에 별·파티클 애니메이션 사용 여부
