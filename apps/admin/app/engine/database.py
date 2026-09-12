"""
데이터베이스 연결 설정 (PostgreSQL)

SQLAlchemy를 사용하여 PostgreSQL 데이터베이스 연결을 설정합니다.
환경 변수(.env 파일)에서 데이터베이스 접속 정보를 읽어옵니다.

환경 변수:
    DB_USER: 데이터베이스 사용자명 (기본값: 'postgres')
    DB_PASSWORD: 데이터베이스 비밀번호
    DB_HOST: 데이터베이스 호스트 (기본값: 'localhost')
    DB_PORT: 데이터베이스 포트 (기본값: '5432')
    DB_NAME: 데이터베이스 이름 (기본값: 'stock_bo')
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# .env 로드: 1) 루트 .env.local, 2) apps/admin/.env
_admin_dir = Path(__file__).resolve().parent.parent.parent  # apps/admin
_root = _admin_dir.parent.parent  # flow 루트
_env_local = _root / ".env.local"
_env_file = _admin_dir / ".env"
if _env_local.exists():
    load_dotenv(dotenv_path=_env_local)
if _env_file.exists():
    load_dotenv(dotenv_path=_env_file)
if not _env_local.exists() and not _env_file.exists():
    load_dotenv()

# 환경 변수에서 DB 접속 정보 가져오기 (PostgreSQL 기본값)
# 빈 문자열 체크: 환경 변수가 빈 문자열로 설정되어 있으면 기본값 사용
def get_env_or_default(key: str, default: str) -> str:
    """환경 변수를 가져오되, 빈 문자열이면 기본값 반환"""
    value = os.getenv(key, default)
    return value if value and value.strip() else default

DB_USER = get_env_or_default("DB_USER", "postgres")
DB_PASSWORD = get_env_or_default("DB_PASSWORD", "")
DB_HOST = get_env_or_default("DB_HOST", "localhost")
DB_PORT = get_env_or_default("DB_PORT", "5432")
DB_NAME = get_env_or_default("DB_NAME", "stock_bo")

# 포트 번호 유효성 검증
try:
    int(DB_PORT)  # 포트가 숫자인지 확인
except ValueError:
    print(f"⚠️ 경고: DB_PORT가 유효하지 않습니다 ('{DB_PORT}'). 기본값 '5432'를 사용합니다.")
    DB_PORT = "5432"

# PostgreSQL 연결 URL
# 형식: postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}
# Railway 공개 호스트(rlwy.net)는 SSL 필요
_raw_url = os.getenv("DATABASE_URL")
if _raw_url and _raw_url.strip():
    # DATABASE_URL이 postgresql:// 이면 psycopg2용으로 변환
    if _raw_url.startswith("postgresql://") and "+" not in _raw_url.split("?")[0]:
        _raw_url = _raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    
    # Railway DATABASE_URL 검증 및 수정: 포트가 없거나 빈 문자열인 경우 처리
    try:
        from urllib.parse import urlparse, urlunparse, quote_plus
        
        parsed = urlparse(_raw_url)
        netloc = parsed.netloc
        
        # netloc에서 호스트와 포트 분리
        # 형식: user:pass@host:port 또는 host:port
        if '@' in netloc:
            # user:pass@host:port 형식
            auth_part, host_port = netloc.rsplit('@', 1)
        else:
            # host:port 형식
            auth_part = None
            host_port = netloc
        
        # 호스트와 포트 분리
        port_fixed = False
        if ':' in host_port:
            host, port = host_port.rsplit(':', 1)
            # 포트가 빈 문자열이거나 숫자가 아니면 기본 포트 사용
            if not port or not port.strip() or not port.isdigit():
                port = DB_PORT
                port_fixed = True
        else:
            # 포트가 없는 경우 기본 포트 추가
            host = host_port
            port = DB_PORT
            port_fixed = True
        
        # 포트가 수정되었으면 URL 재구성
        if port_fixed:
            if auth_part:
                new_netloc = f"{auth_part}@{host}:{port}"
            else:
                new_netloc = f"{host}:{port}"
            parsed = parsed._replace(netloc=new_netloc)
            _raw_url = urlunparse(parsed)
            print(f"⚠️ 경고: DATABASE_URL에 포트가 없어서 기본 포트({port})를 추가했습니다.")
        
        # DB_SSL=true 환경 변수로 SSL 적용 여부 제어
        _use_ssl = os.getenv("DB_SSL", "false").strip().lower() in ("1", "true", "yes")
        if _use_ssl and "sslmode=" not in _raw_url:
            separator = "&" if "?" in _raw_url else "?"
            _raw_url = f"{_raw_url}{separator}sslmode=require"

        SQLALCHEMY_DATABASE_URL = _raw_url
    except Exception as e:
        print(f"⚠️ 경고: DATABASE_URL 파싱 중 오류 ({e}). DB_* 변수를 사용합니다.")
        _use_ssl = os.getenv("DB_SSL", "false").strip().lower() in ("1", "true", "yes")
        _base = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        SQLALCHEMY_DATABASE_URL = f"{_base}?sslmode=require" if _use_ssl else _base
else:
    _use_ssl = os.getenv("DB_SSL", "false").strip().lower() in ("1", "true", "yes")
    _base = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_DATABASE_URL = f"{_base}?sslmode=require" if _use_ssl else _base

# 연결 풀: DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT 환경 변수로 조절 가능.
def _int_env(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)))
        return v if v > 0 else default
    except ValueError:
        return default


_pool_size = _int_env("DB_POOL_SIZE", 10)
_max_overflow = _int_env("DB_MAX_OVERFLOW", 20)
_pool_timeout = _int_env("DB_POOL_TIMEOUT", 60)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_timeout=_pool_timeout,
    pool_recycle=3600,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 의존성 주입용 DB 세션."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
