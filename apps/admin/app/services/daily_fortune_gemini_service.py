"""
오늘의 띠/별자리 운세 서비스 (날짜 시드 순환 방식)

매일 01:00 KST 스케줄러가 띠 12개 + 별자리 12개 운세를 생성하여
daily_fortunes 테이블에 upsert한다.
hash(날짜+key) % pool_size 로 당일 운세 결정론적 선택 — Gemini 불필요.
"""
import hashlib
from datetime import datetime, date
from typing import Optional

import pytz
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.engine.models import DailyFortune
from app.services.fortune_content import ANIMAL_POOL, SIGN_POOL

KST = pytz.timezone("Asia/Seoul")

ZODIAC_ANIMALS = ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"]
ZODIAC_SIGNS = [
    "양자리", "황소자리", "쌍둥이자리", "게자리", "사자자리", "처녀자리",
    "천칭자리", "전갈자리", "사수자리", "염소자리", "물병자리", "물고기자리",
]


def _today_kst() -> date:
    return datetime.now(KST).date()


def _pick_fortune(pool: list[dict], date_str: str, key: str) -> dict:
    """날짜+key 해시로 풀에서 결정론적으로 운세 선택"""
    seed = f"{date_str}{key}".encode()
    idx = int(hashlib.md5(seed).hexdigest(), 16) % len(pool)
    return pool[idx]


def _upsert_fortunes(db: Session, fortune_date: date, fortune_type: str, items: list) -> int:
    """daily_fortunes 테이블에 upsert. 저장된 행 수 반환."""
    key_field = "animal" if fortune_type == "animal" else "sign"
    saved = 0
    for item in items:
        key = item.get(key_field, "").strip()
        fortune_text = item.get("fortune", "").strip()
        investment_tip = item.get("investment_tip", "").strip() or None
        if not key or not fortune_text:
            continue
        stmt = (
            pg_insert(DailyFortune)
            .values(
                fortune_date=fortune_date,
                fortune_type=fortune_type,
                key=key,
                fortune_text=fortune_text,
                investment_tip=investment_tip,
            )
            .on_conflict_do_update(
                constraint="uq_daily_fortune",
                set_={"fortune_text": fortune_text, "investment_tip": investment_tip},
            )
        )
        db.execute(stmt)
        saved += 1
    if saved:
        db.commit()
    return saved


def generate_daily_fortunes(target_date: Optional[date] = None) -> dict:
    """
    띠 12개 + 별자리 12개 운세를 날짜 시드 순환으로 생성해 DB에 저장.
    이미 오늘 데이터가 24개 모두 있으면 스킵.
    """
    today = target_date or _today_kst()
    date_str = today.isoformat()
    result = {"date": date_str, "animal_saved": 0, "sign_saved": 0, "skipped": False}

    db: Session = SessionLocal()
    try:
        existing_count = (
            db.query(DailyFortune)
            .filter(DailyFortune.fortune_date == today)
            .count()
        )
        if existing_count >= 24:
            print(f"ℹ️ {today} 운세 이미 {existing_count}개 존재 — 스킵")
            result["skipped"] = True
            return result

        animal_items = [
            {"animal": a, **_pick_fortune(ANIMAL_POOL[a], date_str, a)}
            for a in ZODIAC_ANIMALS
        ]
        result["animal_saved"] = _upsert_fortunes(db, today, "animal", animal_items)
        print(f"✅ 띠 운세 {result['animal_saved']}개 저장")

        sign_items = [
            {"sign": s, **_pick_fortune(SIGN_POOL[s], date_str, s)}
            for s in ZODIAC_SIGNS
        ]
        result["sign_saved"] = _upsert_fortunes(db, today, "sign", sign_items)
        print(f"✅ 별자리 운세 {result['sign_saved']}개 저장")

        return result
    except Exception as e:
        print(f"❌ 운세 생성 오류: {e}")
        db.rollback()
        return {**result, "error": str(e)}
    finally:
        db.close()


def get_today_fortune(fortune_type: str, key: str) -> Optional[dict]:
    """
    오늘의 운세 조회. DB에 없으면 실시간 생성 후 반환.
    fortune_type: "animal" | "sign"
    key: "쥐" | "양자리" 등
    """
    today = _today_kst()
    db: Session = SessionLocal()
    try:
        row = (
            db.query(DailyFortune)
            .filter(
                DailyFortune.fortune_date == today,
                DailyFortune.fortune_type == fortune_type,
                DailyFortune.key == key,
            )
            .first()
        )
        if row:
            return {
                "fortune_text": row.fortune_text,
                "investment_tip": row.investment_tip,
                "fortune_date": row.fortune_date.isoformat(),
                "key": row.key,
                "fortune_type": row.fortune_type,
            }

        # DB에 없으면 날짜 시드로 실시간 생성 (스케줄러 미실행 시 폴백)
        pool = ANIMAL_POOL.get(key) if fortune_type == "animal" else SIGN_POOL.get(key)
        if not pool:
            return None
        picked = _pick_fortune(pool, today.isoformat(), key)
        return {
            "fortune_text": picked["fortune"],
            "investment_tip": picked.get("investment_tip"),
            "fortune_date": today.isoformat(),
            "key": key,
            "fortune_type": fortune_type,
        }
    finally:
        db.close()
