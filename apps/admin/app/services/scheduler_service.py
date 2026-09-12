"""
FSC 데이터 자동 수집 스케줄러

매일 오후 1:30에 금융위원회 API에서 주식시세정보를 자동으로 수집합니다.
주말(토요일, 일요일)과 공휴일에는 실행하지 않습니다.
최근 3일치 데이터만 유지하고 오래된 데이터는 자동으로 삭제됩니다.
시가총액 상위 200개만 저장합니다.

참고:
- 금융위원회 주식시세 데이터는 당일(오늘) 데이터가 장 마감 직후 바로 생성되지 않을 수 있어,
  자동 수집 시에는 '직전 거래일'(-1, 월요일이면 -3 등) 기준일자를 조회합니다.
"""
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import pytz
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.services.api_service import fsc_api_service, krx_api_service
from app.services.naver_finance_service import naver_finance_service
from app.services.exchange_rate_service import fetch_and_save_exchange_rates
from app.services.yahoo_index_service import (
    fetch_indices,
    upsert_indices_to_db,
    DEFAULT_US_INDICES,
    DEFAULT_KR_INDICES,
    DEFAULT_FOREIGN_INDICES,
)
from app.models import FscStockPrice, FscRisingStock, KrxData


def is_weekend(date: datetime) -> bool:
    """
    주말인지 확인

    Args:
        date: 확인할 날짜

    Returns:
        bool: 토요일(5) 또는 일요일(6)이면 True
    """
    return date.weekday() >= 5


def is_korean_holiday(date: datetime) -> bool:
    """
    한국 공휴일인지 확인

    주요 고정 공휴일과 임시 공휴일을 체크합니다.

    Args:
        date: 확인할 날짜

    Returns:
        bool: 공휴일이면 True
    """
    # 공휴일 목록 (월, 일)
    fixed_holidays = [
        (1, 1),   # 신정
        (3, 1),   # 삼일절
        (5, 5),   # 어린이날
        (6, 6),   # 현충일
        (8, 15),  # 광복절
        (10, 3),  # 개천절
        (10, 9),  # 한글날
        (12, 25), # 크리스마스
    ]

    # 고정 공휴일 체크
    if (date.month, date.day) in fixed_holidays:
        return True

    # 설날, 추석 등 음력 공휴일은 Schedule 테이블에서 확인
    # (일정 관리에서 공휴일을 등록해서 관리)
    db = SessionLocal()
    try:
        from app.models import Schedule
        date_str = date.date()
        schedule = db.query(Schedule).filter(
            Schedule.date == date_str,
            Schedule.type == "api"
        ).first()

        if schedule and "공휴일" in schedule.subject:
            return True
    except Exception as e:
        print(f"⚠️ 공휴일 체크 오류: {e}")
    finally:
        db.close()

    return False


def should_skip_today() -> bool:
    """
    오늘 데이터 수집을 건너뛸지 결정

    주말이나 공휴일이면 True를 반환합니다.

    Returns:
        bool: 건너뛰어야 하면 True
    """
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    if is_weekend(now):
        print(f"⏭️ 주말이므로 데이터 수집을 건너뜁니다. ({now.strftime('%Y-%m-%d %A')})")
        return True

    if is_korean_holiday(now):
        print(f"⏭️ 공휴일이므로 데이터 수집을 건너뜁니다. ({now.strftime('%Y-%m-%d')})")
        return True

    return False


def get_previous_business_day(date: datetime) -> datetime:
    """
    직전 거래일(주말/공휴일 제외) 날짜를 반환합니다.

    - 화~금: 전일(-1)
    - 월요일: 금요일(-3)
    - 공휴일 다음 영업일: 공휴일/주말이 끝날 때까지 더 이전으로 이동
    """
    candidate = date - timedelta(days=1)
    while is_weekend(candidate) or is_korean_holiday(candidate):
        candidate = candidate - timedelta(days=1)
    return candidate


def cleanup_old_fsc_data(db: Session, keep_days: int = 3):
    """
    오래된 FSC 데이터 삭제 (최근 N일치만 유지)

    Args:
        db: 데이터베이스 세션
        keep_days: 유지할 일수 (기본값: 3일)
    """
    try:
        # DB에서 고유한 날짜 목록 조회 (최신순)
        dates = db.query(FscStockPrice.bas_dt)\
            .distinct()\
            .order_by(FscStockPrice.bas_dt.desc())\
            .all()

        date_list = [d[0] for d in dates]

        # 유지할 일수보다 많으면 오래된 날짜 삭제
        if len(date_list) > keep_days:
            dates_to_delete = date_list[keep_days:]

            for old_date in dates_to_delete:
                deleted_count = db.query(FscStockPrice)\
                    .filter(FscStockPrice.bas_dt == old_date)\
                    .delete()
                print(f"🗑️ FSC {old_date} 데이터 삭제 완료 ({deleted_count}건)")

            db.commit()
            print(f"✅ 오래된 FSC 데이터 정리 완료 (최근 {keep_days}일치만 유지)")
        else:
            print(f"ℹ️ 현재 FSC {len(date_list)}일치 데이터 보관 중 (정리 불필요)")

    except Exception as e:
        db.rollback()
        print(f"❌ FSC 데이터 정리 오류: {e}")


def cleanup_old_rising_data(db: Session, keep_days: int = 3):
    """
    오래된 상승종목 데이터 삭제 (최근 N일치만 유지)

    Args:
        db: 데이터베이스 세션
        keep_days: 유지할 일수 (기본값: 3일)
    """
    try:
        dates = db.query(FscRisingStock.bas_dt)\
            .distinct()\
            .order_by(FscRisingStock.bas_dt.desc())\
            .all()

        date_list = [d[0] for d in dates]

        if len(date_list) > keep_days:
            dates_to_delete = date_list[keep_days:]

            for old_date in dates_to_delete:
                deleted_count = db.query(FscRisingStock)\
                    .filter(FscRisingStock.bas_dt == old_date)\
                    .delete()
                print(f"🗑️ 상승종목 {old_date} 데이터 삭제 완료 ({deleted_count}건)")

            db.commit()
            print(f"✅ 오래된 상승종목 데이터 정리 완료 (최근 {keep_days}일치만 유지)")
        else:
            print(f"ℹ️ 현재 상승종목 {len(date_list)}일치 데이터 보관 중 (정리 불필요)")

    except Exception as e:
        db.rollback()
        print(f"❌ 상승종목 데이터 정리 오류: {e}")


def cleanup_old_krx_data(db: Session, keep_days: int = 3):
    """
    오래된 KRX 데이터 삭제 (최근 N일치만 유지)

    Args:
        db: 데이터베이스 세션
        keep_days: 유지할 일수 (기본값: 3일)
    """
    try:
        # 각 데이터 타입별로 날짜 목록 조회
        for data_type in ['kospi', 'kosdaq']:
            dates = db.query(KrxData.bas_dd)\
                .filter(KrxData.data_type == data_type)\
                .distinct()\
                .order_by(KrxData.bas_dd.desc())\
                .all()

            date_list = [d[0] for d in dates]

            # 유지할 일수보다 많으면 오래된 날짜 삭제
            if len(date_list) > keep_days:
                dates_to_delete = date_list[keep_days:]

                for old_date in dates_to_delete:
                    deleted_count = db.query(KrxData)\
                        .filter(
                            KrxData.data_type == data_type,
                            KrxData.bas_dd == old_date
                        )\
                        .delete()
                    print(f"🗑️ KRX {data_type} {old_date} 데이터 삭제 완료 ({deleted_count}건)")

        db.commit()
        print(f"✅ 오래된 KRX 데이터 정리 완료 (최근 {keep_days}일치만 유지)")

    except Exception as e:
        db.rollback()
        print(f"❌ KRX 데이터 정리 오류: {e}")


async def collect_fsc_data():
    """
    FSC 주식시세정보 자동 수집 작업

    매일 오후 1:30에 실행되며, 주말과 공휴일은 건너뜁니다.
    최신 데이터를 자동으로 찾아 수집합니다 (시가총액 상위 200개).
    """
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    print(f"\n{'='*60}")
    print(f"📊 FSC 데이터 자동 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # 주말/공휴일 체크
    if should_skip_today():
        print(f"{'='*60}\n")
        return

    db = SessionLocal()
    try:
        # 최신 데이터 수집 (bas_dt=None으로 호출하면 API가 자동으로 최신 데이터를 찾음)
        print("🔄 금융위원회 API 호출 중... (최신 데이터 확인)")
        data, actual_date = await fsc_api_service.fetch_stock_price_info(
            page_no=1,
            num_of_rows=200,
            bas_dt=None,  # None으로 호출하면 최신 데이터 자동 조회
            db=db
        )

        if data and len(data) > 0 and actual_date:
            print(f"✅ 최신 데이터 수집 완료: {actual_date} ({len(data)}건)")

            # 3일치 데이터만 유지
            cleanup_old_fsc_data(db, keep_days=3)

            print(f"{'='*60}")
            print(f"✅ FSC 데이터 자동 수집 완료")
            print(f"{'='*60}\n")
        else:
            print(f"⚠️ 수집된 데이터가 없습니다.")
            print(f"{'='*60}\n")

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ 데이터 수집 오류: {e}")
        print(f"❌ 상세 오류:\n{error_detail}")
        print(f"{'='*60}\n")
    finally:
        db.close()


async def collect_rising_stocks_data():
    """
    FSC 상승종목 자동 수집 작업

    매일 오후 1:30에 실행되며, 주말과 공휴일은 건너뜁니다.
    최신 데이터를 자동으로 찾아 상승종목을 수집합니다.
    """
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    print(f"\n{'='*60}")
    print(f"📈 FSC 상승종목 자동 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # 주말/공휴일 체크
    if should_skip_today():
        print(f"{'='*60}\n")
        return

    db = SessionLocal()
    try:
        # 최신 데이터 수집 (bas_dt=None으로 호출하면 API가 자동으로 최신 데이터를 찾음)
        print("🔄 금융위원회 API 호출 중... (최신 상승종목 확인 - 10% 이상 상승 종목만)")
        data, actual_date = await fsc_api_service.fetch_rising_stocks(
            bas_dt=None,  # None으로 호출하면 최신 데이터 자동 조회
            db=db,
            min_flt_rt=10.0,  # 10% 이상 상승 종목만
            limit=1000
        )

        if data and len(data) > 0 and actual_date:
            print(f"✅ 최신 상승종목 수집 완료: {actual_date} ({len(data)}건)")

            # 3일치 상승종목 데이터만 유지
            cleanup_old_rising_data(db, keep_days=3)

            print(f"{'='*60}")
            print(f"✅ FSC 상승종목 자동 수집 완료")
            print(f"{'='*60}\n")
        else:
            print(f"⚠️ 수집된 상승종목 데이터가 없습니다.")
            print(f"{'='*60}\n")

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ 상승종목 수집 오류: {e}")
        print(f"❌ 상세 오류:\n{error_detail}")
        print(f"{'='*60}\n")
    finally:
        db.close()


class FscScheduler:
    """
    FSC 데이터 수집 스케줄러

    매일 오후 1:30에 자동으로 데이터를 수집합니다.
    """

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone('Asia/Seoul')

    def start(self):
        """스케줄러 시작"""
        if self.scheduler is not None:
            print("⚠️ 스케줄러가 이미 실행 중입니다.")
            return

        self.scheduler = AsyncIOScheduler(timezone=self.kst)

        # 매일 오후 2:30에 실행 (시가총액 상위)
        self.scheduler.add_job(
            collect_fsc_data,
            trigger=CronTrigger(hour=14, minute=30, timezone=self.kst),
            id='fsc_data_collection',
            name='FSC 주식시세정보 자동 수집',
            replace_existing=True
        )

        # 매일 오후 2:35에 실행 (상승종목) - 시가총액 수집 완료 후 실행
        self.scheduler.add_job(
            collect_rising_stocks_data,
            trigger=CronTrigger(hour=14, minute=35, timezone=self.kst),
            id='fsc_rising_stocks_collection',
            name='FSC 상승종목 자동 수집',
            replace_existing=True
        )

        self.scheduler.start()
        print("✅ FSC 데이터 수집 스케줄러 시작 (매일 14:30)")
        print(f"   - 시가총액 상위: 14:30")
        print(f"   - 상승종목: 14:35")
        print(f"   - 주말 및 공휴일 제외")
        print(f"   - 최근 3일치 데이터만 유지\n")

    def shutdown(self):
        """스케줄러 종료"""
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            print("✅ FSC 데이터 수집 스케줄러 종료")


# 전역 스케줄러 인스턴스
fsc_scheduler = FscScheduler()


# =========================================================
# KRX 데이터 자동 수집 스케줄러
# =========================================================

async def collect_krx_data():
    """
    KRX 지수 데이터 자동 수집 작업 (코스피, 코스닥)
    
    매일 오후 1:30에 실행되며, 주말과 공휴일은 건너뜁니다.
    데이터 수집 후 최근 3일치만 유지하고 나머지는 삭제합니다.
    """
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    print(f"\n{'='*60}")
    print(f"📊 KRX 데이터 자동 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # 주말/공휴일 체크
    if should_skip_today():
        print(f"{'='*60}\n")
        return

    db = SessionLocal()
    try:
        # 코스피 데이터 수집
        print("🔄 코스피 지수 데이터 수집 중...")
        kospi_data = await krx_api_service.fetch_kospi_index(bas_dd=None, db=db)
        
        if kospi_data and len(kospi_data) > 0:
            print(f"✅ 코스피 데이터 수집 완료: {len(kospi_data)}건")
        else:
            print(f"⚠️ 코스피 데이터 수집 실패")

        # 코스닥 데이터 수집
        print("🔄 코스닥 지수 데이터 수집 중...")
        kosdaq_data = await krx_api_service.fetch_kosdaq_index(bas_dd=None, db=db)
        
        if kosdaq_data and len(kosdaq_data) > 0:
            print(f"✅ 코스닥 데이터 수집 완료: {len(kosdaq_data)}건")
        else:
            print(f"⚠️ 코스닥 데이터 수집 실패")

        if (kospi_data and len(kospi_data) > 0) or (kosdaq_data and len(kosdaq_data) > 0):
            # 3일치 데이터만 유지
            cleanup_old_krx_data(db, keep_days=3)

            print(f"{'='*60}")
            print(f"✅ KRX 데이터 자동 수집 완료")
            print(f"{'='*60}\n")
        else:
            print(f"⚠️ 수집된 데이터가 없습니다.")
            print(f"{'='*60}\n")

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ KRX 데이터 수집 오류: {e}")
        print(f"❌ 상세 오류:\n{error_detail}")
        print(f"{'='*60}\n")
    finally:
        db.close()


class KrxScheduler:
    """
    KRX 데이터 수집 스케줄러
    
    매일 오후 1:30에 자동으로 데이터를 수집합니다.
    """

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone('Asia/Seoul')

    def start(self):
        """스케줄러 시작"""
        if self.scheduler is not None:
            print("⚠️ KRX 스케줄러가 이미 실행 중입니다.")
            return

        self.scheduler = AsyncIOScheduler(timezone=self.kst)

        # 매일 오후 2:30에 실행
        self.scheduler.add_job(
            collect_krx_data,
            trigger=CronTrigger(hour=14, minute=30, timezone=self.kst),
            id='krx_data_collection',
            name='KRX 지수 데이터 자동 수집',
            replace_existing=True
        )

        self.scheduler.start()
        print("✅ KRX 데이터 수집 스케줄러 시작 (매일 14:30)")
        print(f"   - 주말 및 공휴일 제외")
        print(f"   - 최근 3일치 데이터만 유지\n")

    def shutdown(self):
        """스케줄러 종료"""
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            print("✅ KRX 데이터 수집 스케줄러 종료")


# 전역 스케줄러 인스턴스
krx_scheduler = KrxScheduler()


# =========================================================
# 네이버 증권 랭킹 데이터 자동 수집 스케줄러
# =========================================================

async def collect_naver_ranking_data():
    """
    네이버 증권 랭킹 데이터 자동 수집 작업
    
    거래량 상위, 거래대금 상위, 검색 상위 데이터를 수집합니다.
    하루에 3번(11시, 16시, 21시) 실행됩니다.
    """
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    current_hour = now.hour
    
    # 수집 시간대 결정
    if current_hour == 11:
        collected_time = '11:00'
    elif current_hour == 16:
        collected_time = '16:00'
    elif current_hour == 21:
        collected_time = '21:00'
    else:
        collected_time = f"{current_hour:02d}:00"
    
    print(f"\n{'='*60}")
    print(f"📊 네이버 증권 랭킹 데이터 자동 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   수집 시간대: {collected_time}")
    print(f"{'='*60}")
    
    # 주말/공휴일 체크
    if should_skip_today():
        print(f"{'='*60}\n")
        return
    
    db = SessionLocal()
    try:
        # 1. 거래량 상위 수집 (코스피, 코스닥, 전체)
        print("🔄 거래량 상위 데이터 수집 중...")
        for market_type in ['kospi', 'kosdaq', 'all']:
            try:
                volume_data = await naver_finance_service.fetch_volume_ranking(
                    market_type=market_type,
                    limit=50
                )
                if volume_data:
                    naver_finance_service.save_ranking_to_db(
                        db=db,
                        ranking_type='volume',
                        market_type=market_type,
                        data=volume_data,
                        collected_time=collected_time
                    )
            except Exception as e:
                print(f"⚠️ 거래량 상위 ({market_type}) 수집 오류: {e}")
        
        # 2. 거래대금 상위 수집 (코스피, 코스닥, 전체)
        print("🔄 거래대금 상위 데이터 수집 중...")
        for market_type in ['kospi', 'kosdaq', 'all']:
            try:
                amount_data = await naver_finance_service.fetch_amount_ranking(
                    market_type=market_type,
                    limit=50
                )
                if amount_data:
                    naver_finance_service.save_ranking_to_db(
                        db=db,
                        ranking_type='amount',
                        market_type=market_type,
                        data=amount_data,
                        collected_time=collected_time
                    )
            except Exception as e:
                print(f"⚠️ 거래대금 상위 ({market_type}) 수집 오류: {e}")
        
        # 3. 검색 상위 수집
        print("🔄 검색 상위 데이터 수집 중...")
        try:
            search_data = await naver_finance_service.fetch_search_ranking(limit=50)
            if search_data:
                naver_finance_service.save_ranking_to_db(
                    db=db,
                    ranking_type='search',
                    market_type='all',
                    data=search_data,
                    collected_time=collected_time
                )
        except Exception as e:
            print(f"⚠️ 검색 상위 수집 오류: {e}")
        
        print(f"{'='*60}")
        print(f"✅ 네이버 증권 랭킹 데이터 자동 수집 완료")
        print(f"{'='*60}\n")
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ 네이버 증권 랭킹 데이터 수집 오류: {e}")
        print(f"❌ 상세 오류:\n{error_detail}")
        print(f"{'='*60}\n")
    finally:
        db.close()


class NaverRankingScheduler:
    """
    네이버 증권 랭킹 데이터 수집 스케줄러
    
    하루에 3번(11시, 16시, 21시) 자동으로 데이터를 수집합니다.
    """
    
    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone('Asia/Seoul')
    
    def start(self):
        """스케줄러 시작"""
        if self.scheduler is not None:
            print("⚠️ 네이버 랭킹 스케줄러가 이미 실행 중입니다.")
            return
        
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        
        # 06:30, 11시, 16시, 21시 (한국시간)
        self.scheduler.add_job(
            collect_naver_ranking_data,
            trigger=CronTrigger(hour=6, minute=30, timezone=self.kst),
            id='naver_ranking_0630',
            name='네이버 증권 랭킹 데이터 수집 (06:30)',
            replace_existing=True
        )
        self.scheduler.add_job(
            collect_naver_ranking_data,
            trigger=CronTrigger(hour=11, minute=0, timezone=self.kst),
            id='naver_ranking_11',
            name='네이버 증권 랭킹 데이터 수집 (11시)',
            replace_existing=True
        )
        self.scheduler.add_job(
            collect_naver_ranking_data,
            trigger=CronTrigger(hour=16, minute=0, timezone=self.kst),
            id='naver_ranking_16',
            name='네이버 증권 랭킹 데이터 수집 (16시)',
            replace_existing=True
        )
        self.scheduler.add_job(
            collect_naver_ranking_data,
            trigger=CronTrigger(hour=21, minute=0, timezone=self.kst),
            id='naver_ranking_21',
            name='네이버 증권 랭킹 데이터 수집 (21시)',
            replace_existing=True
        )
        
        self.scheduler.start()
        print("✅ 네이버 증권 랭킹 데이터 수집 스케줄러 시작 (06:30, 11시, 16시, 21시)")
        print(f"   - 주말 및 공휴일 제외")
        print(f"   - 거래량 상위, 거래대금 상위, 검색 상위 수집\n")
    
    def shutdown(self):
        """스케줄러 종료"""
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            print("✅ 네이버 증권 랭킹 데이터 수집 스케줄러 종료")


# =========================================================
# Yahoo Finance 지수 수집 스케줄러
# =========================================================

async def collect_yahoo_us_indices():
    """
    Yahoo Finance 미국증시 지수 수집/저장
    - 06:20 / 00:00 / 02:00 / 04:00 (KST)
    - 수집 시점의 값으로 일별 최종값 upsert + 7일 유지
    - 주말(토·일) 및 공휴일은 건너뜀
    """
    if should_skip_today():
        print("ℹ️ 주말/공휴일: Yahoo(US) 지수 수집 건너뜀")
        return

    now = datetime.now(pytz.timezone("Asia/Seoul"))
    print(f"\n🌐 Yahoo(US) 지수 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    db = SessionLocal()
    try:
        items = await fetch_indices(DEFAULT_US_INDICES)
        if items:
            upsert_indices_to_db(db, items, collected_at=now, keep_days=7)
            print(f"✅ Yahoo(US) 지수 저장 완료: {len(items)}개")
        else:
            print("⚠️ Yahoo(US) 지수 수집 결과 없음")
    except Exception as e:
        print(f"❌ Yahoo(US) 지수 수집 오류: {e}")
    finally:
        db.close()


async def collect_yahoo_foreign_indices():
    """
    Yahoo Finance 해외지수 수집/저장 (메인 페이지용)
    - 00:00, 05:00, 06:30 (KST)
    - YahooIndexSnapshot에 group='foreign'으로 저장
    - 토요일 오전까지 수집 (미국장 금요일 마감 반영)
    - 일요일/공휴일은 건너뜀
    """
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    if now.weekday() in (0, 6):  # 월요일, 일요일 건너뜀 (미국장은 토요일 KST 기준 마감)
        print("ℹ️ 월요일/일요일: Yahoo(해외) 지수 수집 건너뜀")
        return
    if is_korean_holiday(now):
        print("ℹ️ 공휴일: Yahoo(해외) 지수 수집 건너뜀")
        return

    print(f"\n🌐 Yahoo(해외) 지수 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')} (KST)")
    db = SessionLocal()
    try:
        items = await fetch_indices(DEFAULT_FOREIGN_INDICES)
        if items:
            upsert_indices_to_db(db, items, collected_at=now, keep_days=7)
            print(f"✅ Yahoo(해외) 지수 저장 완료: {len(items)}개")
        else:
            print("⚠️ Yahoo(해외) 지수 수집 결과 없음")
    except Exception as e:
        print(f"❌ Yahoo(해외) 지수 수집 오류: {e}")
    finally:
        db.close()


async def collect_market_closing_summary():
    """
    장마감 시황 생성 및 board/B001 게시 (16:25 KST)
    - 네이버 일자별 수급(investor_day, deal_rank 등)은 16:10 KST 수집 → 그 이후에 실행해야 DB에 데이터가 있음
    - 실행 시 네이버 국내지수를 domestic_index_snapshots에 한 번 더 갱신 후, 마감 시황은 해당 DB(및 Yahoo 폴백) 사용
    - 주말/공휴일은 건너뜀
    """
    if should_skip_today():
        print("ℹ️ 주말/공휴일: 장마감 시황 생성 건너뜀")
        return

    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    print(f"\n{'='*60}")
    print(f"📰 장마감 시황 생성 시작: {now.strftime('%Y-%m-%d %H:%M:%S KST')}")
    print(f"{'='*60}")

    db = SessionLocal()
    try:
        from app.engine import models as _m
        from sqlalchemy import func as _func
        from app.services.domestic_index_service import fetch_and_persist_domestic_indices_sync

        naver_saved = fetch_and_persist_domestic_indices_sync(db)
        print(f"  네이버 국내지수 DB 갱신: {'성공' if naver_saved and naver_saved.get('success') else '실패'}")

        # 진단: Yahoo KR 일별 (폴백용)
        kr_latest = (
            db.query(_func.max(_m.YahooIndexDaily.date))
            .filter(_m.YahooIndexDaily.group == "kr")
            .scalar()
        )
        print(f"  Yahoo KR 일별 최근 날짜: {kr_latest} (오늘: {now.date()})")

        # 진단: 수급 데이터 현황 확인
        bizdate_today = now.strftime("%Y%m%d")
        supply_count = (
            db.query(_m.NaverSupplyData)
            .filter(
                _m.NaverSupplyData.data_type == "deal_rank",
                _m.NaverSupplyData.bizdate == bizdate_today,
            )
            .count()
        )
        print(f"  오늘 수급 deal_rank 데이터: {supply_count}건")

        # [2026-07-08 Gemini 제거] 장마감 시황 AI 생성 비활성화 (비용 절감)
        # from app.services.market_closing_gemini_service import generate_and_post_closing_summary
        # ok = generate_and_post_closing_summary(db, now.date())
        # if ok:
        #     print("✅ 장마감 시황 게시 완료 (pending 상태 - 관리자 승인 후 알림 발송)")
        # else:
        #     print("⚠️ 장마감 시황 생성 실패 (KR지수 없음 또는 Gemini 오류)")
    except Exception as e:
        import traceback
        print(f"❌ 장마감 시황 생성 오류: {e}")
        print(traceback.format_exc())
    finally:
        db.close()
    print(f"{'='*60}\n")


async def collect_yahoo_kr_indices():
    """
    Yahoo Finance 국내지수(코스피/코스닥) 수집/저장
    - 09:10 / 09:40 / 10:10 / 10:40 / 11:10 / 11:40 / 12:10 / 12:40 / 13:10 / 13:40 / 14:10 / 14:40 / 15:10 / 15:40 (KST, 30분 간격 + 장마감)
    - 기존 데이터를 덮어쓰되, 날짜별 마지막 값 유지 (date+symbol upsert)
    - 최대 7일만 보관
    - 주말/공휴일은 건너뜀
    """
    now = datetime.now(pytz.timezone("Asia/Seoul"))
    print(f"\n🇰🇷 Yahoo(KR) 지수 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    if should_skip_today():
        print("ℹ️ 주말/공휴일: Yahoo(KR) 지수 수집 건너뜀")
        return

    db = SessionLocal()
    try:
        items = await fetch_indices(DEFAULT_KR_INDICES)
        if items:
            upsert_indices_to_db(db, items, collected_at=now, keep_days=7)
            print(f"✅ Yahoo(KR) 지수 저장 완료: {len(items)}개")
        else:
            print("⚠️ Yahoo(KR) 지수 수집 결과 없음")
    except Exception as e:
        print(f"❌ Yahoo(KR) 지수 수집 오류: {e}")
    finally:
        db.close()


class YahooIndexScheduler:
    """
    Yahoo Finance 지수 수집 스케줄러
    """
    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone('Asia/Seoul')

    def start(self):
        if self.scheduler is not None:
            print("⚠️ Yahoo 지수 스케줄러가 이미 실행 중입니다.")
            return

        self.scheduler = AsyncIOScheduler(timezone=self.kst)

        # 해외지수(메인용): 00:00, 05:00, 06:30 (KST)
        self.scheduler.add_job(
            collect_yahoo_foreign_indices,
            CronTrigger(hour=0, minute=0, timezone=self.kst),
            id="yahoo_foreign_0000",
            name="Yahoo 해외지수 (00:00)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            collect_yahoo_foreign_indices,
            CronTrigger(hour=5, minute=0, timezone=self.kst),
            id="yahoo_foreign_0500",
            name="Yahoo 해외지수 (05:00)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            collect_yahoo_foreign_indices,
            CronTrigger(hour=6, minute=30, timezone=self.kst),
            id="yahoo_foreign_0630",
            name="Yahoo 해외지수 (06:30)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        # 해외지수 토요일 07:00 - 미국 금요일 마감 확정 데이터 수집
        self.scheduler.add_job(
            collect_yahoo_foreign_indices,
            CronTrigger(hour=7, minute=0, day_of_week="sat", timezone=self.kst),
            id="yahoo_foreign_sat_0700",
            name="Yahoo 해외지수 토요일 (07:00)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        # 시황 보고서(B001)는 BO 시장 데이터 > 보고서 작성에서 관리자가 직접 작성·등록 (/admin/market-report)

        # US: 06:20, 00:00, 02:00, 04:00 (KST)
        self.scheduler.add_job(
            collect_yahoo_us_indices,
            CronTrigger(hour=6, minute=20, timezone=self.kst),
            id="yahoo_us_0620",
            name="Yahoo US Indices (06:20)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            collect_yahoo_us_indices,
            CronTrigger(hour=0, minute=0, timezone=self.kst),
            id="yahoo_us_0000",
            name="Yahoo US Indices (00:00)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            collect_yahoo_us_indices,
            CronTrigger(hour=2, minute=0, timezone=self.kst),
            id="yahoo_us_0200",
            name="Yahoo US Indices (02:00)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            collect_yahoo_us_indices,
            CronTrigger(hour=4, minute=0, timezone=self.kst),
            id="yahoo_us_0400",
            name="Yahoo US Indices (04:00)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        # KR: 09:10 ~ 15:10 (30분 간격) + 15:40 장마감 (KST)
        for _h, _m, _id in [
            (9,  10, "yahoo_kr_0910"),
            (9,  40, "yahoo_kr_0940"),
            (10, 10, "yahoo_kr_1010"),
            (10, 40, "yahoo_kr_1040"),
            (11, 10, "yahoo_kr_1110"),
            (11, 40, "yahoo_kr_1140"),
            (12, 10, "yahoo_kr_1210"),
            (12, 40, "yahoo_kr_1240"),
            (13, 10, "yahoo_kr_1310"),
            (13, 40, "yahoo_kr_1340"),
            (14, 10, "yahoo_kr_1410"),
            (14, 40, "yahoo_kr_1440"),
            (15, 10, "yahoo_kr_1510"),
            (15, 40, "yahoo_kr_1540"),
        ]:
            self.scheduler.add_job(
                collect_yahoo_kr_indices,
                CronTrigger(hour=_h, minute=_m, timezone=self.kst),
                id=_id,
                name=f"Yahoo KR Indices ({_h:02d}:{_m:02d})",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
        # 장마감 시황 생성: 16:25 (16:10 네이버 일자별 수급 수집 후 + 15:40 KR 지수 반영)
        self.scheduler.add_job(
            collect_market_closing_summary,
            CronTrigger(hour=16, minute=25, timezone=self.kst),
            id="market_closing_summary",
            name="장마감 시황 생성 (16:25)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )

        self.scheduler.start()
        print("✅ Yahoo 지수 수집 스케줄러 시작")
        print("   - 해외(메인): 00:00 / 05:00 / 06:30 (KST)")
        print("   - US: 06:20 / 00:00 / 02:00 / 04:00 (KST)")
        print("   - KR: 09:10 ~ 15:10 (30분 간격) / 15:40 장마감 (KST)")
        print("   - 장마감 시황: 16:25 (KST, 주말/공휴일 제외, 16:10 수급 수집 이후)")
        print("   - 최근 7일치만 유지\n")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            print("✅ Yahoo 지수 수집 스케줄러 종료")


yahoo_index_scheduler = YahooIndexScheduler()


# =========================================================
# 환율 수집 스케줄러 (30분마다)
# =========================================================

async def collect_exchange_rates():
    """30분마다 Yahoo Finance에서 환율 수집 후 DB 저장"""
    now = datetime.now(pytz.timezone("Asia/Seoul"))
    print(f"\n💱 환율 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    db = SessionLocal()
    try:
        ok = await fetch_and_save_exchange_rates(db)
        if ok:
            print("✅ 환율 저장 완료")
        else:
            print("⚠️ 환율 수집 결과 없음")
    except Exception as e:
        print(f"❌ 환율 수집 오류: {e}")
    finally:
        db.close()


class ExchangeRateScheduler:
    """환율 30분마다 수집 스케줄러"""
    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            print("⚠️ 환율 스케줄러가 이미 실행 중입니다.")
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        self.scheduler.add_job(
            collect_exchange_rates,
            CronTrigger(minute="0,30", timezone=self.kst),
            id="exchange_rate",
            name="환율 수집 (30분마다)",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.start()
        print("✅ 환율 수집 스케줄러 시작 (30분마다)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            print("✅ 환율 수집 스케줄러 종료")


exchange_rate_scheduler = ExchangeRateScheduler()


# =========================================================
# 네이버 수급 동향 수집 스케줄러
# 08:30 ~ 20:30, 30분 간격, 월~금, 공휴일 제외
# =========================================================

async def collect_naver_supply_data():
    """
    네이버 수급 동향 수집 (investor_time, program_time) → Gemini AI 요약.

    한 슬롯마다 `SUPPLY_SOURCES_TIME_ONLY`로 **all · kospi · kosdaq** 각각 저장한다.
    수급 요약 카드·`supply_summary_gemini_service`·차트는 **kospi / kosdaq** 행만 쓴다.
    (`all`은 합산 시장 페이지 등 다른 용도·백워드 호환용으로 동일 스케줄에서 함께 수집.)
    """
    from app.services.naver_supply_service import collect_investor_program_supply_data
    # [2026-07-08 Gemini 제거] 수급 Gemini 요약 서비스 비활성화
    # from app.services.supply_summary_gemini_service import generate_and_save_supply_summary
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    bizdate = now.strftime("%Y%m%d")
    collected_time = f"{now.hour:02d}:{now.minute:02d}"

    print(f"\n{'='*60}")
    print(f"📊 네이버 수급 동향 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    if should_skip_today():
        print("⏭️ 주말/공휴일 - 수급 동향 수집 건너뜀")
        return

    db = SessionLocal()
    try:
        # 수집·Gemini 저장 모두 동일 collected_time 사용 (DB naver_supply_data ↔ supply_summary_ai 정합)
        count = await collect_investor_program_supply_data(db, bizdate, collected_time)
        print(f"✅ 수급 동향 수집 완료: {count}건")

        # [2026-07-08 Gemini 제거] 수급 Gemini AI 요약 비활성화 (비용 절감)
        # if count > 0:
        #     try:
        #         n_ai = generate_and_save_supply_summary(db, bizdate, collected_time)
        #         if n_ai:
        #             print(f"✅ 수급 Gemini AI 요약 저장: {n_ai}건 (코스피·코스닥)")
        #     except Exception as gemini_err:
        #         import traceback
        #         print(f"⚠️ 수급 Gemini AI 요약 오류: {gemini_err}")
        #         print(traceback.format_exc())
    except Exception as e:
        import traceback
        print(f"❌ 수급 동향 수집 오류: {e}")
        print(traceback.format_exc())
    finally:
        db.close()
    print(f"{'='*60}\n")


async def collect_naver_supply_daily():
    """
    네이버 수급 동향 일자별 전체 수집 (investor_day, program_day, deal_rank 포함).
    장마감 후 16:10 1회 실행 → supply 페이지 메인 테이블 데이터 갱신.
    """
    from app.services.naver_supply_service import collect_all_supply_data
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)

    if should_skip_today():
        print("⏭️ 주말/공휴일 - 일자별 수급 수집 건너뜀")
        return

    print(f"\n{'='*60}")
    print(f"📊 네이버 수급 일자별 전체 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    db = SessionLocal()
    try:
        bizdate = now.strftime("%Y%m%d")
        count = await collect_all_supply_data(db, bizdate=bizdate, collected_time="16:00")
        print(f"✅ 일자별 수급 수집 완료: {count}건")
    except Exception as e:
        import traceback
        print(f"❌ 일자별 수급 수집 오류: {e}")
        print(traceback.format_exc())
    finally:
        db.close()
    print(f"{'='*60}\n")


async def collect_advancing_declining_count_scheduled():
    """
    네이버 상승/하락 종목 수 수집 (ADR 지표 계산용).
    08:40 ~ 15:40: 30분 간격 (장중) 실행
    """
    from app.services.naver_supply_service import collect_advancing_declining_count
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)

    if should_skip_today():
        return

    print(f"📈 ADR 데이터 수집: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    db = SessionLocal()
    try:
        await collect_advancing_declining_count(db)
        print(f"✅ ADR 데이터 수집 완료")
    except Exception as e:
        import traceback
        print(f"❌ ADR 데이터 수집 오류: {e}")
        print(traceback.format_exc())
    finally:
        db.close()


class NaverSupplyScheduler:
    """
    네이버 수급 동향 데이터 수집 스케줄러
    - 08:40 ~ 15:40: 30분 간격 (장중) — investor_time, program_time
    - 16:40 ~ 20:40: 1시간 간격 (장마감 후) — investor_time, program_time
    - 16:10: 1회 — investor_day, program_day, deal_rank 전체 수집
    실행 시각: 08:40, 09:10, 09:40, 10:10, 10:40, 11:10, 11:40, 12:10, 12:40,
              13:10, 13:40, 14:10, 14:40, 15:10, 15:40, 16:10(일자별), 16:40, 17:40, 18:40, 19:40, 20:40
    """
    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            print("⚠️ 수급 동향 스케줄러가 이미 실행 중입니다.")
            return

        self.scheduler = AsyncIOScheduler(timezone=self.kst)

        # 08:40 ~ 15:40: 30분 간격 (08:40 + 09:10~15:40)
        self.scheduler.add_job(
            collect_naver_supply_data,
            trigger=CronTrigger(hour=8, minute=40, timezone=self.kst),
            id="naver_supply_0840",
            name="수급 동향 수집 (08:40)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            collect_naver_supply_data,
            trigger=CronTrigger(hour="9-15", minute="10,40", timezone=self.kst),
            id="naver_supply_intraday",
            name="수급 동향 수집 (09:10~15:40, 30분 간격)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        # 16:10: 장마감 후 일자별 전체 수집 (investor_day, program_day, deal_rank)
        self.scheduler.add_job(
            collect_naver_supply_daily,
            trigger=CronTrigger(hour=16, minute=10, timezone=self.kst),
            id="naver_supply_daily",
            name="수급 일자별 전체 수집 (16:10)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        # 16:40 ~ 20:40: 1시간 간격
        self.scheduler.add_job(
            collect_naver_supply_data,
            trigger=CronTrigger(hour="16-20", minute=40, timezone=self.kst),
            id="naver_supply_after",
            name="수급 동향 수집 (16:40~20:40, 1시간 간격)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        # 08:40 ~ 15:40: 30분 간격 (ADR 지표 수집)
        self.scheduler.add_job(
            collect_advancing_declining_count_scheduled,
            trigger=CronTrigger(hour=8, minute=40, timezone=self.kst),
            id="adr_advancing_0840",
            name="ADR 데이터 수집 (08:40)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.add_job(
            collect_advancing_declining_count_scheduled,
            trigger=CronTrigger(hour="9-15", minute="10,40", timezone=self.kst),
            id="adr_advancing_intraday",
            name="ADR 데이터 수집 (09:10~15:40, 30분 간격)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        self.scheduler.start()
        print("✅ 네이버 수급 동향 스케줄러 시작 (08:40~15:40 30분 / 16:10 일자별 / 16:40~20:40 1시간, ADR 추가, 월~금)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            print("✅ 네이버 수급 동향 스케줄러 종료")


naver_supply_scheduler = NaverSupplyScheduler()

# 전역 스케줄러 인스턴스
naver_ranking_scheduler = NaverRankingScheduler()


# =========================================================
# 네이버 뉴스 주가 영향 뉴스 수집 스케줄러
# =========================================================

async def collect_naver_stock_news():
    """
    네이버 뉴스 API로 주가 직접 영향 뉴스 수집
    평일(월~금) 08:30, 12:30, 19:30 (KST) 실행
    수집 직후 동일 세션에서 금일 이슈 Gemini 요약을 실행한다.
    (시장의 목소리 Gemini 요약은 토큰 절감으로 비활성화 — 아래 try 블록 주석 참고)
    수주, 실적발표, 배당, 연구개발, 기술이전, 유상증자 등 키워드 기반 필터링
    최근 2일치 뉴스만 유지
    """
    from app.services.naver_news_service import naver_news_service

    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    print(f"\n{'='*60}")
    print(f"네이버 주가 영향 뉴스 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    if should_skip_today():
        print(f"{'='*60}\n")
        return

    db = SessionLocal()
    try:
        news_list = await naver_news_service.fetch_stock_impact_news()
        if news_list:
            saved = naver_news_service.save_news_to_db(db, news_list)
            print(f"신규 뉴스 저장: {saved}건")

        naver_news_service.cleanup_old_news(db)

        # [2026-07-08 Gemini 제거] 금일 이슈 AI 요약 비활성화 (비용 절감)
        # try:
        #     from app.services.daily_issue_gemini_service import generate_and_save_daily_issue_summary
        #
        #     if generate_and_save_daily_issue_summary(db, now.date()):
        #         print("✅ 금일 이슈 Gemini 요약 저장 (뉴스 수집 직후)")
        #     else:
        #         print("ℹ️ 금일 이슈 요약 스킵 (당일 뉴스 없음 또는 Gemini 실패)")
        # except Exception as issue_err:
        #     import traceback
        #
        #     print(f"⚠️ 금일 이슈 요약 오류: {issue_err}")
        #     print(traceback.format_exc())

        # 비활성화: 시장의 목소리 AI 요약(Gemini) — 토큰 소모 큼. 재개 시 아래 주석 해제.
        # try:
        #     from app.services.market_voice_service import fetch_and_summarize_news
        #
        #     cleanup_old_market_voices(db, keep_days=2)
        #     mv_result = await fetch_and_summarize_news(db)
        #     print(
        #         f"✅ 시장의 목소리 수집 (뉴스 직후): "
        #         f"조회 {mv_result.get('fetched', 0)}건, 신규 {mv_result.get('saved', 0)}건"
        #     )
        # except Exception as mv_err:
        #     import traceback
        #
        #     print(f"⚠️ 시장의 목소리 수집 오류: {mv_err}")
        #     print(traceback.format_exc())

        print(f"{'='*60}")
        print(f"네이버 주가 영향 뉴스 수집 완료")
        print(f"{'='*60}\n")
    except Exception as e:
        import traceback
        print(f"네이버 주가 영향 뉴스 수집 오류: {e}")
        print(traceback.format_exc())
        print(f"{'='*60}\n")
    finally:
        db.close()


class NaverNewsScheduler:
    """
    네이버 주가 영향 뉴스 수집 스케줄러
    평일(월~금) 08:30, 12:30, 19:30 (KST) 수집 + 금일 이슈 Gemini (시장의 목소리 Gemini는 비활성화)
    """

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            print("네이버 뉴스 스케줄러가 이미 실행 중입니다.")
            return

        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        self.scheduler.add_job(
            collect_naver_stock_news,
            trigger=CronTrigger(day_of_week="mon-fri", hour="8,12,19", minute=30, timezone=self.kst),
            id="naver_stock_news_collection",
            name="주가 영향 뉴스 수집 (08:30/12:30/19:30, 월~금)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.start()
        print("네이버 주가 영향 뉴스 스케줄러 시작 (08:30/12:30/19:30 + 이슈 Gemini, 월~금; 시장의 목소리 Gemini 비활성화)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            print("네이버 주가 영향 뉴스 스케줄러 종료")


naver_news_scheduler = NaverNewsScheduler()


# 금일 이슈·시장의 목소리: collect_naver_stock_news() 안에서 뉴스 저장 직후 실행 (별도 스케줄 없음)

# =========================================================
# 시장의 목소리 — 오래된 행 정리 (스케줄 잡은 뉴스 수집 파이프라인에서 호출)
# =========================================================

def cleanup_old_market_voices(db: Session, keep_days: int = 2):
    """2일 이상 지난 market_voices 레코드 삭제 (pending/approved 모두)"""
    try:
        from app.models import MarketVoice
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        deleted = db.query(MarketVoice).filter(MarketVoice.created_at < cutoff).delete()
        db.commit()
        if deleted:
            print(f"🗑️ 시장의 목소리 오래된 항목 삭제: {deleted}건 (2일 초과)")
    except Exception as e:
        db.rollback()
        print(f"❌ 시장의 목소리 정리 오류: {e}")


# =========================================================
# 투자은행 뉴스 (GS, MS, JPM) - 매일 12:00
# =========================================================

async def collect_investment_bank_news():
    """Yahoo Finance에서 GS/MS/JPM 한국증시 관련 뉴스 수집"""
    from app.services.investment_bank_news_service import fetch_and_save_investment_bank_news

    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    print(f"\n[투자은행 뉴스] 수집 시작: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    db = SessionLocal()
    try:
        result = await fetch_and_save_investment_bank_news(db)
        print(f"[투자은행 뉴스] 완료: {result.get('saved', 0)}건 저장")
    except Exception as e:
        import traceback
        print(f"[투자은행 뉴스] 오류: {e}")
        traceback.print_exc()
    finally:
        db.close()


class InvestmentBankNewsScheduler:
    """투자은행 뉴스 수집 스케줄러 (매일 12:00 KST) — 현재 Gemini 번역 토큰 절감을 위해 비활성화."""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        # 비활성화: 투자은행 뉴스 Gemini 번역 — 토큰 소모 큼. 재개 시 아래 주석 해제.
        # self.scheduler = AsyncIOScheduler(timezone=self.kst)
        # self.scheduler.add_job(
        #     collect_investment_bank_news,
        #     trigger=CronTrigger(hour=12, minute=0, timezone=self.kst),
        #     id="investment_bank_news_collection",
        #     name="투자은행 뉴스 수집 (12:00, 매일)",
        #     replace_existing=True,
        #     max_instances=1,
        #     coalesce=True,
        #     misfire_grace_time=600,
        # )
        # self.scheduler.start()
        # print("투자은행 뉴스 스케줄러 시작 (12:00, 매일)")
        print("ℹ️ 투자은행 뉴스 스케줄러 비활성화 (Gemini 번역 토큰 절감)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


investment_bank_news_scheduler = InvestmentBankNewsScheduler()


# =========================================================
# 증권사 목표가 상향 뉴스 - 매일 1회 (08:30 KST)
#   08:30 : 전일 08:30 KST ~ 당일 08:30 KST (24시간치 리포트)
# =========================================================

async def collect_target_price_news():
    """08:30 수집: 전일 08:30 KST ~ 당일 08:30 KST 게시된 목표가 기사만 처리 (24시간)"""
    if should_skip_today():
        print("ℹ️ 주말/공휴일: 목표가 뉴스 수집 건너뜀 (08:30)")
        return

    from datetime import timezone as _tz, timedelta as _td
    from app.services.target_price_news_service import fetch_and_post_target_price_news

    kst = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst)
    print(f"\n[목표가 뉴스 08:30] 수집·등록 시작: {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")

    # 전일 08:30 KST ~ 지금 (24시간)
    yesterday = now_kst.date() - _td(days=1)
    after_kst = kst.localize(datetime(yesterday.year, yesterday.month, yesterday.day, 8, 30, 0))
    after_utc = after_kst.astimezone(_tz.utc)
    before_utc = now_kst.astimezone(_tz.utc)

    db = SessionLocal()
    try:
        result = await fetch_and_post_target_price_news(db, after_dt=after_utc, before_dt=before_utc)
        print(f"[목표가 뉴스 08:30] 완료: fetched={result['fetched']}, items={result.get('items', 0)}, posted={result['posted']}")
    except Exception as e:
        import traceback
        print(f"[목표가 뉴스 08:30] 오류: {e}")
        traceback.print_exc()
    finally:
        db.close()


class TargetPriceNewsScheduler:
    """증권사 목표가 상향 뉴스 수집 스케줄러 (매일 1회: 08:30 KST)"""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        # 08:30 - 전일 08:30 ~ 당일 08:30 (24시간)
        self.scheduler.add_job(
            collect_target_price_news,
            trigger=CronTrigger(hour=8, minute=30, timezone=self.kst),
            id="target_price_news_0830",
            name="목표가 상향 뉴스 수집·등록 (08:30, 전일 08:30~)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
        self.scheduler.start()
        print("목표가 상향 뉴스 스케줄러 시작 (08:30 전일 08:30~당일 08:30, 24시간)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


target_price_news_scheduler = TargetPriceNewsScheduler()


# =========================================================
# 네이버증권 상승종목 수집 스케줄러 (12:00 / 15:40 / 20:30 KST)
# =========================================================

async def collect_naver_rising_stocks():
    """네이버증권 상승률 10%이상 종목 수집 (코스피/코스닥)"""
    if should_skip_today():
        return
    from app.database import SessionLocal
    from app.services.naver_rising_stock_service import collect_and_save
    db = SessionLocal()
    try:
        result = await collect_and_save(db)
        print(f"[상승종목] 수집 완료: 코스피 {result.get('kospi', 0)}개, 코스닥 {result.get('kosdaq', 0)}개")
    except Exception as e:
        print(f"[상승종목] 수집 오류: {e}")
    finally:
        db.close()


class NaverRisingScheduler:
    """네이버증권 상승종목 수집 스케줄러 (매일 12:00 / 15:40 / 20:30 KST)"""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        for hour, minute, slot_id in [
            (12,  0, "1200"),
            (15, 40, "1540"),
            (20, 30, "2030"),
        ]:
            self.scheduler.add_job(
                collect_naver_rising_stocks,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=self.kst),
                id=f"naver_rising_{slot_id}",
                name=f"네이버 상승종목 수집 ({hour:02d}:{minute:02d})",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
        self.scheduler.start()
        print("✅ 네이버 상승종목 스케줄러 시작 (12:00 / 15:40 / 20:30 KST)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


naver_rising_scheduler = NaverRisingScheduler()


# =========================================================
# 조건검색 (기술적 지표 기반 종목 스크리닝)
# 평일 20:30 KST, 시총 상위 500종목 대상
# =========================================================

async def collect_stock_screening():
    """조건검색 실행 (스케줄러에서 호출)"""
    if should_skip_today():
        return
    from app.database import SessionLocal
    from app.services.stock_screening_service import collect_and_save
    db = SessionLocal()
    try:
        result = await collect_and_save(db)
        print(f"[조건검색] 수집 완료: 코스피 {result.get('kospi', 0)}건, 코스닥 {result.get('kosdaq', 0)}건")
    except Exception as e:
        print(f"[조건검색] 수집 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


class StockScreeningScheduler:
    """조건검색 스케줄러 (평일 20:30 KST, 시총 상위 500종목)"""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        self.scheduler.add_job(
            collect_stock_screening,
            trigger=CronTrigger(day_of_week="mon-fri", hour=20, minute=30, timezone=self.kst),
            id="stock_screening_2030",
            name="조건검색 스크리닝 (20:30, 월~금)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
        self.scheduler.start()
        print("✅ 조건검색 스케줄러 시작 (20:30 KST, 평일)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


stock_screening_scheduler = StockScreeningScheduler()


# =========================================================
# 종베 검색식 (종가 베팅 스크리닝)
# 평일 15:00 KST, 동시호가(15:20) 전 결과 확보
# =========================================================

async def collect_jongbe_screening():
    """종베 검색식 실행 (스케줄러에서 호출)"""
    if should_skip_today():
        return
    from app.database import SessionLocal
    from app.services.jongbe_screening_service import collect_and_save_jongbe
    db = SessionLocal()
    try:
        result = await collect_and_save_jongbe(db)
        print(f"[종베] 수집 완료: 코스피 {result.get('kospi', 0)}건, 코스닥 {result.get('kosdaq', 0)}건")
    except Exception as e:
        print(f"[종베] 수집 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


class JongbeScreeningScheduler:
    """종베 검색식 스케줄러 (평일 15:00 KST, 동시호가 전 결과 확보)"""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        self.scheduler.add_job(
            collect_jongbe_screening,
            trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=0, timezone=self.kst),
            id="jongbe_screening_1500",
            name="종베 검색식 (15:00, 월~금)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
        self.scheduler.start()
        print("✅ 종베 검색식 스케줄러 시작 (15:00 KST, 평일)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


jongbe_screening_scheduler = JongbeScreeningScheduler()


# =========================================================
# 밥그릇(U자형 반등) 검색식
# 평일 20:45 KST, 224일 이평선 기준 추세 전환 패턴
# =========================================================

async def collect_ricebowl_screening():
    """밥그릇 검색식 실행 (스케줄러에서 호출)"""
    if should_skip_today():
        return
    from app.database import SessionLocal
    from app.services.ricebowl_screening_service import collect_and_save_ricebowl
    db = SessionLocal()
    try:
        result = await collect_and_save_ricebowl(db)
        print(f"[밥그릇] 수집 완료: 코스피 {result.get('kospi', 0)}건, 코스닥 {result.get('kosdaq', 0)}건")
    except Exception as e:
        print(f"[밥그릇] 수집 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


class RicebowlScreeningScheduler:
    """밥그릇 검색식 스케줄러 (평일 20:45 KST, 224일 이평선 기준)"""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        self.scheduler.add_job(
            collect_ricebowl_screening,
            trigger=CronTrigger(day_of_week="mon-fri", hour=20, minute=45, timezone=self.kst),
            id="ricebowl_screening_2045",
            name="밥그릇 검색식 (20:45, 월~금)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
        self.scheduler.start()
        print("✅ 밥그릇 검색식 스케줄러 시작 (20:45 KST, 평일)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


ricebowl_screening_scheduler = RicebowlScreeningScheduler()


# =========================================================
# 급등 예상 (주도주 매물 소화 및 돌파)
# 평일 20:55 KST, 거래대금 상위 150 종목 대상
# =========================================================

async def collect_breakout_screening():
    """급등 예상 검색식 실행 (스케줄러에서 호출)"""
    if should_skip_today():
        return
    from app.database import SessionLocal
    from app.services.breakout_screening_service import collect_and_save_breakout
    db = SessionLocal()
    try:
        result = await collect_and_save_breakout(db)
        print(f"[급등] 수집 완료: 코스피 {result.get('kospi', 0)}건, 코스닥 {result.get('kosdaq', 0)}건")
    except Exception as e:
        print(f"[급등] 수집 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


class BreakoutScreeningScheduler:
    """급등 예상 스케줄러 (평일 20:55 KST, 거래대금 상위 150종목)"""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        self.scheduler.add_job(
            collect_breakout_screening,
            trigger=CronTrigger(day_of_week="mon-fri", hour=20, minute=55, timezone=self.kst),
            id="breakout_screening_2055",
            name="급등 예상 검색식 (20:55, 월~금)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
        self.scheduler.start()
        print("✅ 급등 예상 검색식 스케줄러 시작 (20:55 KST, 평일)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


breakout_screening_scheduler = BreakoutScreeningScheduler()


# =========================================================
# 투자자 심리지수
# 매일 09:00, 12:00, 18:00 KST (주말·공휴일 포함 — 커뮤니티·뉴스 기반 지표는 장중 여부와 무관)
# =========================================================

async def collect_and_analyze_sentiment():
    """심리지수 파이프라인 (스케줄러에서 호출). 주말/공휴일에도 실행."""
    from app.database import SessionLocal
    from app.services.community_sentiment_service import collect_community_posts
    from app.services.sentiment_analysis_service import generate_sentiment_snapshot
    db = SessionLocal()
    try:
        # 1. 커뮤니티 게시글 수집
        counts = await collect_community_posts(db)
        print(f"[심리지수] 커뮤니티 수집: 네이버 {counts.get('naver', 0)}건, DC {counts.get('dc', 0)}건")
        # 2. 7개 지표 산출 + 종합지수 저장
        snapshot = await generate_sentiment_snapshot(db)
        if snapshot:
            print(f"[심리지수] 스냅샷 저장: {snapshot.composite_score}점 ({snapshot.label})")
    except Exception as e:
        print(f"[심리지수] 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


class SentimentScheduler:
    """투자자 심리지수 스케줄러 (매일 09:00, 12:00, 18:00 KST, 주말·공휴일 포함)"""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        for hour in [9, 12, 18]:
            self.scheduler.add_job(
                collect_and_analyze_sentiment,
                trigger=CronTrigger(hour=hour, minute=0, timezone=self.kst),
                id=f"sentiment_{hour:02d}00",
                name=f"심리지수 ({hour:02d}:00, 매일·주말·공휴일 포함)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=600,
            )
        self.scheduler.start()
        print("심리지수 스케줄러 시작 (09:00, 12:00, 18:00 KST, 매일·주말·공휴일 포함)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


sentiment_scheduler = SentimentScheduler()


# =========================================================
# 네이버 검색어 트렌드 스케줄러
# =========================================================

async def collect_naver_trend_daily():
    """일간 트렌드 수집 (하루 3회)"""
    if should_skip_today():
        return
    from app.database import SessionLocal
    from app.services.naver_trend_service import collect_search_trends
    db = SessionLocal()
    try:
        await collect_search_trends(db, time_unit="date")
    except Exception as e:
        print(f"[검색트렌드] 일간 수집 오류: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


async def collect_naver_trend_weekly():
    """주간 트렌드 수집 (주 1회 월요일)"""
    from app.database import SessionLocal
    from app.services.naver_trend_service import collect_search_trends
    db = SessionLocal()
    try:
        await collect_search_trends(db, time_unit="week")
    except Exception as e:
        print(f"[검색트렌드] 주간 수집 오류: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


async def collect_naver_trend_monthly():
    """월간 트렌드 수집 (매월 1일)"""
    from app.database import SessionLocal
    from app.services.naver_trend_service import collect_search_trends
    db = SessionLocal()
    try:
        await collect_search_trends(db, time_unit="month")
    except Exception as e:
        print(f"[검색트렌드] 월간 수집 오류: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


class NaverTrendScheduler:
    """네이버 검색어 트렌드 스케줄러
    - 일간: 평일 09:00, 13:00, 18:00
    - 주간: 매주 월요일 08:00
    - 월간: 매월 1일 08:00
    """

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)

        # 일간 (평일 3회)
        for hour in [9, 13, 18]:
            self.scheduler.add_job(
                collect_naver_trend_daily,
                trigger=CronTrigger(day_of_week="mon-fri", hour=hour, minute=0, timezone=self.kst),
                id=f"naver_trend_daily_{hour:02d}",
                name=f"검색트렌드 일간 ({hour}:00)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=600,
            )

        # 주간 (월요일 08:00)
        self.scheduler.add_job(
            collect_naver_trend_weekly,
            trigger=CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=self.kst),
            id="naver_trend_weekly",
            name="검색트렌드 주간 (월 08:00)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )

        # 월간 (매월 1일 08:00)
        self.scheduler.add_job(
            collect_naver_trend_monthly,
            trigger=CronTrigger(day=1, hour=8, minute=0, timezone=self.kst),
            id="naver_trend_monthly",
            name="검색트렌드 월간 (1일 08:00)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )

        self.scheduler.start()
        print("검색트렌드 스케줄러 시작 (일간 09/13/18, 주간 월08, 월간 1일08)")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None


naver_trend_scheduler = NaverTrendScheduler()


class DailyFortuneScheduler:
    """매일 01:00 KST 띠/별자리 운세 Gemini 생성"""

    def __init__(self):
        self.scheduler = None
        self.kst = pytz.timezone("Asia/Seoul")

    def start(self):
        if self.scheduler is not None:
            print("⚠️ 운세 스케줄러가 이미 실행 중입니다.")
            return
        self.scheduler = AsyncIOScheduler(timezone=self.kst)
        self.scheduler.add_job(
            self._generate,
            trigger=CronTrigger(hour=1, minute=0, timezone=self.kst),
            id="daily_fortune_generate",
            name="오늘의 띠/별자리 운세 생성",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        print("✅ 운세 스케줄러 시작 (매일 01:00 KST)")
        # 오늘 데이터가 없으면 시작 시 즉시 생성
        import asyncio as _asyncio
        try:
            loop = _asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._generate_if_needed())
        except Exception:
            pass

    async def _generate_if_needed(self):
        """오늘 운세가 없을 때만 생성 (서버 시작 시 호출)"""
        try:
            from datetime import datetime
            from app.database import SessionLocal
            from app.engine.models import DailyFortune
            today = datetime.now(self.kst).date()
            db = SessionLocal()
            try:
                count = db.query(DailyFortune).filter(DailyFortune.fortune_date == today).count()
            finally:
                db.close()
            if count < 24:
                print(f"ℹ️ 오늘({today}) 운세 데이터 {count}개 — 즉시 생성 시작")
                await self._generate()
        except Exception as e:
            print(f"⚠️ 운세 시작 시 체크 오류: {e}")

    async def _generate(self):
        try:
            from app.services.daily_fortune_gemini_service import generate_daily_fortunes
            result = generate_daily_fortunes()
            print(f"🔮 운세 생성 완료: {result}")
        except Exception as e:
            print(f"❌ 운세 스케줄러 오류: {e}")

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            print("✅ 운세 스케줄러 종료")


daily_fortune_scheduler = DailyFortuneScheduler()
