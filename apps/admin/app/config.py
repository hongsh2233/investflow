"""
애플리케이션 설정

이 모듈은 환경 변수에서 애플리케이션 설정을 로드합니다.
.env 파일에 다음 변수들을 설정해야 합니다.

필수 환경 변수:
    ADMIN_EMAIL: 초기 관리자 이메일
    ADMIN_PW: 초기 관리자 비밀번호
    SECRET_TOKEN: 세션 인증 토큰
    DB_USER: 데이터베이스 사용자명
    DB_PASSWORD: 데이터베이스 비밀번호
    DB_HOST: 데이터베이스 호스트
    DB_PORT: 데이터베이스 포트
    DB_NAME: 데이터베이스 이름

선택적 환경 변수:
    AUTH_COOKIE_NAME: 인증 쿠키 이름 (기본값: 'bo_session_id')
    JWT_SECRET_KEY: JWT 토큰 암호화 키 (기본값: SECRET_TOKEN 또는 기본값)
    DATA_GO_KR_API_KEY: 공공데이터포털 API 인증키
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 디렉토리: admin (BASE_DIR), 모노레포 루트 (ROOT)
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT = BASE_DIR.parent.parent  # flow 루트

# 업로드 파일 루트 (빌드/실행 경로와 무관하게 동일한 경로 사용 → 이미지 엑박 방지)
UPLOADS_DIR = BASE_DIR / "uploads"
ENV_LOCAL_ROOT = ROOT / ".env.local"
ENV_FILE = BASE_DIR / ".env"

# 1) 루트 .env.local 먼저 로드 (web + admin 공용)
if ENV_LOCAL_ROOT.exists():
    load_dotenv(dotenv_path=ENV_LOCAL_ROOT)
    print(f".env.local 로드 완료 (루트): {ENV_LOCAL_ROOT}")
# 2) admin/.env 있으면 로드 (admin 전용, 루트에 없는 값 보충)
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
    print(f".env 로드 완료 (admin): {ENV_FILE}")
if not ENV_LOCAL_ROOT.exists() and not ENV_FILE.exists():
    load_dotenv()
    print("경고: .env.local(루트) 또는 .env(admin) 없음. 기본 위치에서 시도합니다.")

# 관리자 계정 초기화 전용 환경 변수
# ⚠️ 이 값은 서버 최초 실행 시 DB에 관리자 계정을 생성하는 용도로만 사용됩니다.
# 실행 이후 로그인 인증은 DB(admin_users 테이블) 기반으로만 동작합니다.
# 반드시 .env 또는 배포 환경의 Secrets/Variables에 설정하세요.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")  # 초기 최고 관리자 이메일 (초기화 전용)
ADMIN_PW = os.environ.get("ADMIN_PW")  # 초기 최고 관리자 비밀번호 (초기화 전용)

# 인증 설정
AUTH_COOKIE_NAME = os.environ.get("AUTH_COOKIE_NAME", "bo_session_id")  # 인증 쿠키 이름
SECRET_TOKEN = os.environ.get("SECRET_TOKEN")  # 세션 인증 토큰

# 하드코딩 제거: 프로덕션에서는 환경 변수 필수. 개발 환경에서만 임시 토큰 허용
_IS_PRODUCTION = os.environ.get("APP_ENV", "").lower() == "production"
if not SECRET_TOKEN:
    if _IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_TOKEN이 설정되지 않았습니다. "
            "서버 환경 변수(APP_ENV=production)에서 SECRET_TOKEN을 설정하세요. "
            "예: SECRET_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
        )
    import secrets
    SECRET_TOKEN = secrets.token_urlsafe(32)
    print("⚠️ SECRET_TOKEN 미설정. 개발용 임시 토큰 사용 (재시작 시 변경됨)")

# JWT 설정 (REST API 인증용)
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_TOKEN
JWT_ALGORITHM = "HS256"  # JWT 알고리즘
JWT_ACCESS_TOKEN_EXPIRE_HOURS = 1  # Access Token 만료 시간 (1시간) - 짧게 설정하여 보안 강화
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30  # Refresh Token 만료 시간 (30일) - 긴 기간으로 설정

# 공공데이터포털 API 설정
DATA_GO_KR_API_KEY = os.environ.get("DATA_GO_KR_API_KEY")  # 공공데이터포털 API 인증키

# Open DART(금융감독원 전자공시) API 설정
OPENDART_API_KEY = os.environ.get("OPENDART")  # Open DART 인증키 (40자리)

# Google Gemini API (관리자 스케줄·요약 전반)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# google-genai generate_content 모델명 (필요 시 환경 변수로 덮어쓰기)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# 네이버 검색 API 설정 (뉴스 검색)
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")       # 네이버 API 클라이언트 ID
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")  # 네이버 API 클라이언트 시크릿

# 네이버 데이터랩 검색어 트렌드 API
NAVER_TREND_CLIENT_ID = os.environ.get("NAVER_TREND_CLIENT_ID")
NAVER_TREND_CLIENT_SECRET = os.environ.get("NAVER_TREND_CLIENT_SECRET")

# 네이버 증시 캘린더 (구 JSON·PC URL이 404로 폐기된 상태가 일반적 → 기본 off, 필요 시 true)
NAVER_CALENDAR_ENABLED = os.environ.get("NAVER_CALENDAR_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Resend 이메일 발송 (비밀번호 재설정 등)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
# 발신 이메일 (Resend 도메인 검증 필요. 미설정 시 onboarding@resend.dev 사용 - 수신 제한 있음)
PASSWORD_RESET_FROM_EMAIL = os.environ.get("PASSWORD_RESET_FROM_EMAIL", "플로우 <onboarding@resend.dev>")


# 디버깅: API 키 로드 확인 (서버 시작 시 한 번만 출력)
# 보안: API 키 미리보기는 콘솔에 출력하지 않음
if DATA_GO_KR_API_KEY:
    print(f"DATA_GO_KR_API_KEY 로드됨 (길이: {len(DATA_GO_KR_API_KEY)}자)")
else:
    print("경고: DATA_GO_KR_API_KEY가 설정되지 않았습니다.")

if OPENDART_API_KEY:
    print(f"OPENDART API 키 로드됨 (길이: {len(OPENDART_API_KEY)}자)")
else:
    print("경고: OPENDART(공모청약 DART) API 키가 설정되지 않았습니다.")

if NAVER_CLIENT_ID:
    print(f"NAVER_CLIENT_ID 로드됨 (길이: {len(NAVER_CLIENT_ID)}자)")
else:
    print("경고: NAVER_CLIENT_ID가 설정되지 않았습니다. 네이버 뉴스 검색 기능을 사용하려면 설정이 필요합니다.")


