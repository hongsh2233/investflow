"""
공통 의존성 함수들

이 모듈은 FastAPI의 의존성 주입(Dependency Injection)을 사용하여
인증 및 권한 확인을 수행하는 함수들을 제공합니다.

주요 함수:
    - get_current_user: 쿠키 기반 인증 (웹 페이지용)
    - get_current_member: 회원 세션 확인
    - get_current_user_from_token: JWT 토큰 기반 인증 (REST API용)
"""
import os
import json
# from fastapi import Request, Depends, HTTPException, status
from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from pathlib import Path
from app.database import get_db
from app import models
from app.utils import verify_token

# 루트 .env.local 우선 로드 (config/engine과 동일)
_root = Path(__file__).resolve().parent.parent.parent.parent  # flow 루트
_env_local = _root / ".env.local"
if _env_local.exists():
    load_dotenv(dotenv_path=_env_local)
else:
    load_dotenv()

# --- API 시크릿 키 (프론트엔드 NEXT_PUBLIC_X_API_KEY와 동일 값) ---
# 하드코딩 제거: 환경 변수에서만 로드. 프로덕션에서는 Railway Variables 필수.
API_SECRET_KEY = os.environ.get("NEXT_PUBLIC_X_API_KEY")

if os.environ.get("RAILWAY_ENVIRONMENT") and not API_SECRET_KEY:
    raise RuntimeError(
        "NEXT_PUBLIC_X_API_KEY가 설정되지 않았습니다. "
        "Railway Variables에서 설정하세요."
    )

# 기존 설정들...
AUTH_COOKIE_NAME = os.environ.get("AUTH_COOKIE_NAME", "bo_session_id")
MEMBER_COOKIE_NAME = "member_session"
security = HTTPBearer()

# SECRET_TOKEN은 config에서 가져오기 (기본값 생성 로직 포함)
from app.config import SECRET_TOKEN

# --- 신규: 시크릿 키 검증 함수 (프론트엔드 API용) ---
async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    HTTP 헤더의 X-API-KEY를 확인하여 데이터를 반환합니다.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # 공백 제거 후 비교
    x_api_key = x_api_key.strip()
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return x_api_key

# Bearer 토큰 스키마 (JWT 인증용)
security = HTTPBearer()


async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    인증 확인 함수 (쿠키 기반 - 웹 페이지용)

    관리자 인증 쿠키를 확인하여 로그인 상태를 검증합니다.

    Args:
        request: FastAPI Request 객체
        db: 데이터베이스 세션

    Returns:
        AdminUser: 관리자 사용자 객체 (인증 성공 시), None (인증 실패 시)
    """
    # SECRET_TOKEN이 없으면 인증 실패
    if not SECRET_TOKEN:
        return None

    session_id = request.cookies.get(AUTH_COOKIE_NAME)
    if not session_id or session_id != SECRET_TOKEN:
        return None

    # 환경변수에서 관리자 이메일 가져오기
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if not admin_email:
        return None

    user = db.query(models.AdminUser).filter(models.AdminUser.email == admin_email).first()
    return user


async def get_current_user_or_api_key_for_fsc(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
):
    """
    쿠키(관리자) 또는 X-API-KEY(프론트엔드)로 인증.
    /api/right-schedule 등 FE에서 호출하는 FSC API용.
    """
    if x_api_key and x_api_key.strip() == API_SECRET_KEY:
        return True
    session_id = request.cookies.get(AUTH_COOKIE_NAME)
    if session_id and session_id == SECRET_TOKEN:
        return session_id
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다.")


async def get_current_member(request: Request):
    """
    회원 세션 확인 함수
    
    회원 인증 쿠키를 확인하여 회원 로그인 상태를 검증합니다.
    
    Args:
        request: FastAPI Request 객체
    
    Returns:
        dict: 회원 정보 (인증 성공 시), None (인증 실패 시)
    """
    member_cookie = request.cookies.get(MEMBER_COOKIE_NAME)
    if not member_cookie:
        return None
    try:
        member_data = json.loads(member_cookie)
        return member_data
    except:
        return None


async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    JWT 토큰에서 사용자 정보를 가져오는 함수 (API용)
    Authorization: Bearer <token> 형식으로 요청해야 함
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰에 사용자 정보가 없습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # DB에서 사용자 확인
    user = db.query(models.AdminUser).filter(models.AdminUser.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


# Bearer 토큰 스키마 (선택적 인증용 - 에러 없음)
security_optional = HTTPBearer(auto_error=False)


member_bearer_optional = HTTPBearer(auto_error=False)


async def get_current_member_from_bearer_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(member_bearer_optional),
    db: Session = Depends(get_db),
):
    """
    회원 JWT (type=member, sub=email). 관리자 토큰과 구분.
    게시글 조회 시 X-API-KEY와 함께 Authorization Bearer로 전달 가능.
    """
    if credentials is None:
        return None
    try:
        payload = verify_token(credentials.credentials)
        if not payload or payload.get("type") != "member":
            return None
        email = payload.get("sub")
        if not email:
            return None
        return db.query(models.Member).filter(models.Member.email == email).first()
    except Exception:
        return None


async def require_current_member(
    member=Depends(get_current_member_from_bearer_optional),
):
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return member


async def get_current_user_from_token_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: Session = Depends(get_db)
):
    """
    JWT 토큰에서 사용자 정보를 가져오는 함수 (선택적 - API Key와 함께 사용)
    Authorization 헤더가 없으면 None을 반환합니다.
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if payload is None:
            return None
        
        email: str = payload.get("sub")
        if email is None:
            return None
        
        # DB에서 사용자 확인
        user = db.query(models.AdminUser).filter(models.AdminUser.email == email).first()
        return user
    except:
        return None


async def get_admin_session_or_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    token_user=Depends(get_current_user_from_token_optional),
    db: Session = Depends(get_db),
):
    """
    BO 대시보드(쿠키)·관리자 Bearer·X-API-KEY(BFF/서버) 중 하나로 인증.
    스크리닝 조회 등 프론트 BFF가 API 키로 호출할 때 사용.
    """
    if x_api_key is not None and x_api_key.strip():
        if x_api_key.strip() == API_SECRET_KEY:
            return True
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    if token_user:
        return token_user
    session_user = await get_current_user(request, db)
    if session_user:
        return session_user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )

