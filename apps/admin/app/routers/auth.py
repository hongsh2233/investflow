"""
인증 관련 라우터
"""
import os
import re
import time
from fastapi import APIRouter, Form, Request, Depends, HTTPException, Header, status
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from datetime import timedelta, datetime
import secrets

from app import models, utils
from app.database import get_db
from app.dependencies import get_current_user, AUTH_COOKIE_NAME
from app.config import (
    JWT_ACCESS_TOKEN_EXPIRE_HOURS,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_TOKEN,
    RESEND_API_KEY,
    PASSWORD_RESET_FROM_EMAIL,
)
from app.dependencies import API_SECRET_KEY
from app.utils.profile_generator import generate_profile
from app.utils.login_attempts import check_locked, record_failure, clear_attempts
from app.utils.safe_logger import safe_log_error
from app.services.member_point_service import (
    grant_signup_bonus,
    grant_daily_login_bonus,
    grant_jubti_first_bonus,
    grant_mbti_first_bonus,
    grant_zodiac_animal_first_bonus,
    grant_zodiac_sign_first_bonus,
    charge_screening_pick_if_needed,
)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def get_effective_grade(member) -> str:
    """만료일이 지난 등급은 regular로 반환"""
    grade = getattr(member, "grade", "regular") or "regular"
    if grade == "regular":
        return "regular"
    expires_at = getattr(member, "grade_expires_at", None)
    if expires_at is not None:
        now = datetime.utcnow()
        expires_naive = expires_at.replace(tzinfo=None) if expires_at.tzinfo else expires_at
        if expires_naive < now:
            return "regular"
    return grade


# API 토큰 발급용 요청 모델
class TokenRequest(BaseModel):
    username: str
    password: str


# 소셜 로그인 회원 등록 요청 모델
class SocialLoginRequest(BaseModel):
    provider: str  # 'google' (naver/kakao 소셜 로그인 비활성화)
    email: str
    name: str
    provider_id: str  # 소셜 로그인 제공자의 사용자 고유 ID


# 일반 회원가입 요청 모델 (서버 측 검증으로 보안 강화)
class MemberSignupRequest(BaseModel):
    email: str
    password: str
    nickname: str = None  # 프론트에서 전달한 닉네임 (없으면 서버에서 자동 생성)
    name: str = None  # 사용자 이름 (아이디 찾기에 사용)

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("이메일을 입력해주세요.")
        v = v.strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v):
            raise ValueError("올바른 이메일 형식이 아닙니다.")
        if len(v) > 255:
            raise ValueError("이메일이 너무 깁니다.")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if not v:
            raise ValueError("비밀번호를 입력해주세요.")
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        if len(v) > 128:
            raise ValueError("비밀번호가 너무 깁니다.")
        return v

    @field_validator("name")
    @classmethod
    def name_strip_and_length(cls, v: Optional[str]) -> Optional[str]:
        """DB Member.name String(50)과 정합. 공백만이면 None(프로필 기본 이름 사용)."""
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        if len(s) > 50:
            raise ValueError("이름은 50자 이하여야 합니다.")
        return s


# 일반 회원 로그인 요청 모델
class MemberLoginRequest(BaseModel):
    email: str
    password: str


class MemberLoginResponse(BaseModel):
    success: bool
    message: str
    member_id: int = None
    email: str = None
    nickname: str = None
    profile_image: str = None
    grade: str = "regular"
    access_token: str = None
    point_balance: int = 0


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class SocialLoginResponse(BaseModel):
    success: bool
    message: str
    member_id: int = None
    has_nickname: bool = False  # 닉네임이 설정되어 있는지 여부
    nickname: str = None  # 닉네임
    profile_image: str = None  # 프로필 이미지
    grade: str = "regular"  # 'regular' | 'vip' | 'family'
    access_token: str = None
    point_balance: int = 0


# 회원 정보 업데이트 요청 모델
class UpdateMemberRequest(BaseModel):
    email: str
    nickname: str
    profile_image: str = None


class ScreeningPickChargeRequest(BaseModel):
    """스크리닝 표 담기 시 순위가 무료 구간을 넘으면 포인트 차감"""
    email: str
    stock_code: str
    rank: int
    screening_date: str
    screening_type: str  # ichimoku | jongbe | ricebowl | breakout


# 주BTI 성향 저장 요청 모델
class JubtiUpdateRequest(BaseModel):
    email: str
    jubti_type: str  # A | D | N | I

    @field_validator("jubti_type")
    @classmethod
    def jubti_type_must_be_valid(cls, v: str) -> str:
        if v not in ("A", "D", "N", "I"):
            raise ValueError("jubti_type must be one of A, D, N, I")
        return v


VALID_MBTI = {
    "INTJ", "INTP", "ENTJ", "ENTP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ESTP", "ENFJ", "ENFP",
    "INFJ", "INFP", "ESFP", "ISFP",
}

VALID_ZODIAC_ANIMALS = {"쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"}

VALID_ZODIAC_SIGNS = {
    "양자리", "황소자리", "쌍둥이자리", "게자리", "사자자리", "처녀자리",
    "천칭자리", "전갈자리", "사수자리", "염소자리", "물병자리", "물고기자리",
}


class MbtiUpdateRequest(BaseModel):
    email: str
    mbti_type: str

    @field_validator("mbti_type")
    @classmethod
    def mbti_must_be_valid(cls, v: str) -> str:
        if v.upper() not in VALID_MBTI:
            raise ValueError(f"mbti_type must be one of {VALID_MBTI}")
        return v.upper()


class ZodiacUpdateRequest(BaseModel):
    email: str
    zodiac_animal: Optional[str] = None
    zodiac_sign: Optional[str] = None

    @field_validator("zodiac_animal")
    @classmethod
    def animal_must_be_valid(cls, v):
        if v is not None and v not in VALID_ZODIAC_ANIMALS:
            raise ValueError(f"zodiac_animal must be one of {VALID_ZODIAC_ANIMALS}")
        return v

    @field_validator("zodiac_sign")
    @classmethod
    def sign_must_be_valid(cls, v):
        if v is not None and v not in VALID_ZODIAC_SIGNS:
            raise ValueError(f"zodiac_sign must be one of {VALID_ZODIAC_SIGNS}")
        return v


# 관심종목 관련 요청/응답 모델
class FavoriteStockRequest(BaseModel):
    email: str
    stock_code: str


class FavoriteStockResponse(BaseModel):
    success: bool
    message: str
    favorite_stocks: list[str] = []


class CharacterInfo(BaseModel):
    name: str
    image: str


class CharactersResponse(BaseModel):
    success: bool
    message: str
    characters: list[CharacterInfo] = []


@router.get("/", response_class=HTMLResponse)
async def read_root(user=Depends(get_current_user)):
    """초기 접속 화면 - 로그인 시 대시보드로 리다이렉트"""
    if user:
        return RedirectResponse(url="/admin/dashboard")
    # 로그인되지 않은 경우 로그인 페이지로 리다이렉트
    return RedirectResponse(url="/login")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 화면"""
    # SECRET_TOKEN이 없으면 로그인 불가
    if not SECRET_TOKEN:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
          <meta charset="UTF-8"/>
          <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
          <title>Flow BO - 오류</title>
          <link rel="icon" href="/static/image/favicon.svg" type="image/svg+xml" />
          <style>
            @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
            *{box-sizing:border-box;margin:0;padding:0}
            body{font-family:'Pretendard',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#1a2332;padding:1rem}
            .error-card{max-width:400px;width:100%;background:#fff;border-radius:16px;padding:2.5rem 2rem;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.15)}
            .error-icon{width:56px;height:56px;background:#fff5f5;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;margin-bottom:1rem}
            .error-icon svg{width:28px;height:28px;color:#e53e3e}
            h2{font-size:1.25rem;font-weight:700;color:#2d3748;margin-bottom:.5rem}
            p{font-size:.875rem;color:#718096;line-height:1.6}
          </style>
        </head>
        <body>
          <div class="error-card">
            <div class="error-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/>
                <line x1="12" x2="12.01" y1="16" y2="16"/>
              </svg>
            </div>
            <h2>서버 설정 오류</h2>
            <p>SECRET_TOKEN이 설정되지 않았습니다.<br/>서버 관리자에게 문의하세요.</p>
          </div>
        </body>
        </html>
        """, status_code=500)
    
    # 이미 로그인된 경우 대시보드로 리다이렉트
    if request.cookies.get(AUTH_COOKIE_NAME) == SECRET_TOKEN:
        return RedirectResponse(url="/admin/dashboard")
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <meta name="robots" content="noindex, nofollow, noarchive, nosnippet" />
      <meta name="googlebot" content="noindex, nofollow" />
      <meta name="description" content="관리자 로그인 (비공개)" />
      <title>Flow BO - 로그인</title>
      <link rel="icon" href="/static/image/favicon.svg" type="image/svg+xml" />
      <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

        *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

        body{
          font-family:'Pretendard',-apple-system,BlinkMacSystemFont,system-ui,'Apple SD Gothic Neo',sans-serif;
          min-height:100vh;
          display:flex;
          align-items:center;
          justify-content:center;
          background:#1a2332;
          background-image:
            radial-gradient(ellipse at 20% 50%,rgba(52,152,219,.12) 0%,transparent 60%),
            radial-gradient(ellipse at 80% 20%,rgba(46,204,113,.08) 0%,transparent 50%);
          padding:1rem;
          -webkit-font-smoothing:antialiased;
        }

        /* ── 카드 ── */
        .login-card{
          width:100%;max-width:400px;
          background:#fff;
          border-radius:16px;
          box-shadow:0 4px 6px rgba(0,0,0,.04),0 20px 60px rgba(0,0,0,.15);
          overflow:hidden;
          animation:slideUp .5s ease-out;
        }
        @keyframes slideUp{
          from{opacity:0;transform:translateY(24px)}
          to{opacity:1;transform:translateY(0)}
        }

        /* ── 헤더 ── */
        .login-header{
          background:linear-gradient(135deg,#2c3e50 0%,#34495e 100%);
          padding:2.25rem 2rem 2rem;
          text-align:center;
          position:relative;
          overflow:hidden;
        }
        .login-header::before{
          content:'';position:absolute;
          width:200px;height:200px;
          background:rgba(255,255,255,.04);
          border-radius:50%;
          top:-80px;right:-60px;
        }
        .login-header::after{
          content:'';position:absolute;
          width:120px;height:120px;
          background:rgba(255,255,255,.03);
          border-radius:50%;
          bottom:-40px;left:-30px;
        }

        .logo-icon{
          width:56px;height:56px;
          background:rgba(255,255,255,.12);
          border-radius:14px;
          display:inline-flex;align-items:center;justify-content:center;
          margin-bottom:.875rem;
          backdrop-filter:blur(4px);
          border:1px solid rgba(255,255,255,.1);
        }
        .logo-icon svg{
          width:28px;height:28px;color:#fff;
        }

        .login-header h1{
          font-size:1.375rem;font-weight:700;
          color:#fff;letter-spacing:-.01em;
          margin-bottom:.25rem;
        }
        .login-header p{
          font-size:.8125rem;
          color:rgba(255,255,255,.55);
          font-weight:400;
        }

        /* ── 폼 영역 ── */
        .login-body{
          padding:2rem;
        }

        .field{
          margin-bottom:1.125rem;
        }
        .field label{
          display:block;
          font-size:.8125rem;font-weight:500;
          color:#4a5568;
          margin-bottom:.375rem;
          letter-spacing:-.01em;
        }
        .input-wrap{
          position:relative;
        }
        .input-wrap svg{
          position:absolute;
          left:.875rem;top:50%;transform:translateY(-50%);
          width:1.125rem;height:1.125rem;
          color:#a0aec0;
          pointer-events:none;
          transition:color .2s;
        }
        .input-wrap input{
          width:100%;
          padding:.75rem .875rem .75rem 2.75rem;
          font-size:.9375rem;
          line-height:1.5;
          border:1.5px solid #e2e8f0;
          border-radius:10px;
          background:#f7fafc;
          outline:none;
          font-family:inherit;
          transition:border-color .2s,background .2s,box-shadow .2s;
        }
        .input-wrap input::placeholder{
          color:#a0aec0;
        }
        .input-wrap input:hover{
          border-color:#cbd5e0;
        }
        .input-wrap input:focus{
          border-color:#3498db;
          background:#fff;
          box-shadow:0 0 0 3px rgba(52,152,219,.12);
        }
        .input-wrap:focus-within svg{
          color:#3498db;
        }

        /* ── 로그인 버튼 ── */
        .login-btn{
          width:100%;
          padding:.8125rem;
          font-size:1rem;font-weight:600;
          color:#fff;
          background:linear-gradient(135deg,#2c3e50 0%,#3498db 100%);
          border:none;border-radius:10px;
          cursor:pointer;
          transition:transform .15s,box-shadow .25s,opacity .15s;
          margin-top:.5rem;
          font-family:inherit;
          position:relative;
          overflow:hidden;
        }
        .login-btn::after{
          content:'';position:absolute;
          top:0;left:0;width:100%;height:100%;
          background:linear-gradient(135deg,transparent 0%,rgba(255,255,255,.08) 100%);
          opacity:0;transition:opacity .25s;
        }
        .login-btn:hover{
          transform:translateY(-1px);
          box-shadow:0 6px 20px rgba(52,152,219,.3);
        }
        .login-btn:hover::after{
          opacity:1;
        }
        .login-btn:active{
          transform:translateY(0) scale(.98);
        }

        /* ── 에러 메시지 ── */
        .error-msg{
          display:none;
          background:#fff5f5;
          color:#c53030;
          font-size:.8125rem;
          padding:.625rem .875rem;
          border-radius:8px;
          border:1px solid #fed7d7;
          margin-bottom:1rem;
          text-align:center;
        }
        .error-msg.show{
          display:block;
          animation:shake .4s ease-in-out;
        }
        @keyframes shake{
          0%,100%{transform:translateX(0)}
          25%{transform:translateX(-6px)}
          75%{transform:translateX(6px)}
        }

        /* ── 푸터 ── */
        .login-footer{
          text-align:center;
          padding:0 2rem 1.75rem;
        }
        .login-footer p{
          font-size:.75rem;
          color:#a0aec0;
        }

        /* ── 반응형 ── */
        @media(max-width:480px){
          .login-card{max-width:100%;border-radius:12px}
          .login-header{padding:1.75rem 1.5rem 1.5rem}
          .login-body{padding:1.5rem}
        }
      </style>
    </head>
    <body>
      <div class="login-card">
        <!-- 헤더 -->
        <div class="login-header">
          <div class="logo-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 20V10"/>
              <path d="M18 20V4"/>
              <path d="M6 20v-4"/>
            </svg>
          </div>
          <h1>Flow BO</h1>
          <p>Back Office Management</p>
        </div>

        <!-- 폼 -->
        <div class="login-body">
          <div id="errorMsg" class="error-msg">
            이메일 또는 비밀번호를 확인해주세요.
          </div>

          <form action="/login" method="post" id="loginForm">
            <div class="field">
              <label for="username">이메일</label>
              <div class="input-wrap">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="20" height="16" x="2" y="4" rx="2"/>
                  <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                </svg>
                <input type="email" id="username" name="username" placeholder="admin@example.com"
                       required autocomplete="email" autofocus />
              </div>
            </div>
            <div class="field">
              <label for="password">비밀번호</label>
              <div class="input-wrap">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                <input type="password" id="password" name="password" placeholder="비밀번호를 입력하세요"
                       required autocomplete="current-password" />
              </div>
            </div>
            <button type="submit" class="login-btn">로그인</button>
          </form>
        </div>

        <!-- 푸터 -->
        <div class="login-footer">
          <p>&copy; Flow BO &middot; 관리자 전용</p>
        </div>
      </div>

      <script>
        // URL에 error 파라미터가 있으면 에러 메시지 표시
        const params = new URLSearchParams(window.location.search);
        const err = params.get('error');
        const msgEl = document.getElementById('errorMsg');
        if (err === '1') {
          msgEl.textContent = '이메일 또는 비밀번호를 확인해주세요.';
          msgEl.classList.add('show');
        } else if (err === 'locked') {
          msgEl.textContent = params.get('msg') || '너무 많은 로그인 시도입니다. 15분 후 다시 시도해 주세요.';
          msgEl.classList.add('show');
        }
      </script>
    </body>
    </html>
    """


def _get_client_ip(request: Request) -> str:
    """클라이언트 IP 추출 (X-Forwarded-For, X-Real-IP 지원)"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("X-Real-IP") or request.client.host if request.client else "unknown"


@router.post("/login")
async def do_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """로그인 처리"""
    ip = _get_client_ip(request)
    locked, msg = check_locked(db, username, ip)
    if locked:
        from urllib.parse import quote
        return RedirectResponse(url=f"/login?error=locked&msg={quote(msg or '')}", status_code=303)

    user = db.query(models.AdminUser).filter(models.AdminUser.email == username).first()
    
    if not user or not utils.verify_password(password, user.hashed_password):
        record_failure(db, username, ip)
        return RedirectResponse(url="/login?error=1", status_code=303)

    clear_attempts(db, username, ip)
    
    # 로그인 성공 시 관리자 세션 쿠키 설정 (30분 유효)
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=SECRET_TOKEN,
        httponly=True,
        secure=bool(os.environ.get("RAILWAY_ENVIRONMENT")),
        max_age=30 * 60,  # 30분
        samesite="lax",
    )
    # 로그인 시각 전달용 쿠키 (프론트엔드 세션 타이머 표시용, httponly 아님)
    login_time_ms = int(time.time() * 1000)
    response.set_cookie(
        key="bo_login_time",
        value=str(login_time_ms),
        httponly=False,
        secure=bool(os.environ.get("RAILWAY_ENVIRONMENT")),
        max_age=30 * 60,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    """로그아웃"""
    response = RedirectResponse(url="/")
    response.delete_cookie(AUTH_COOKIE_NAME)
    response.delete_cookie("bo_login_time")
    return response


@router.post("/login/extend")
async def extend_login(request: Request):
    """
    로그인 연장 처리
    
    - 현재 세션 쿠키가 유효한 경우에만 연장
    - 쿠키 만료 시간을 다시 30분으로 연장
    """
    current_session = request.cookies.get(AUTH_COOKIE_NAME)
    if not current_session or current_session != SECRET_TOKEN:
        return JSONResponse(
            {"success": False, "message": "세션이 이미 만료되었습니다."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    login_time_ms = int(time.time() * 1000)
    response = JSONResponse({
        "success": True,
        "message": "로그인이 연장되었습니다.",
        "login_time": login_time_ms,
    })
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=SECRET_TOKEN,
        httponly=True,
        secure=bool(os.environ.get("RAILWAY_ENVIRONMENT")),
        max_age=30 * 60,  # 30분 재설정
        samesite="lax",
    )
    response.set_cookie(
        key="bo_login_time",
        value=str(login_time_ms),
        httponly=False,
        secure=bool(os.environ.get("RAILWAY_ENVIRONMENT")),
        max_age=30 * 60,
        samesite="lax",
    )
    return response


# =========================================================
# REST API용 토큰 발급 엔드포인트
# =========================================================

def _generate_token_response(user: models.AdminUser, db: Session) -> TokenResponse:
    """
    JWT Access Token과 Refresh Token 생성 및 응답 생성 (공통 함수)
    """
    # Access Token 생성 (짧은 만료 시간)
    access_token_expires = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = utils.create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    # Refresh Token 생성 및 DB 저장
    refresh_token = utils.create_refresh_token()
    refresh_token_expires = timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    expires_at = datetime.utcnow() + refresh_token_expires
    
    # 기존 Refresh Token이 있으면 삭제 (한 사용자당 하나의 활성 Refresh Token만 유지)
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user.id
    ).delete()
    
    # 새 Refresh Token 저장
    db_refresh_token = models.RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=expires_at
    )
    db.add(db_refresh_token)
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        refresh_expires_in=int(refresh_token_expires.total_seconds())
    )


@router.post("/api/auth/token", response_model=TokenResponse)
async def api_token(
    http_request: Request,
    token_request: TokenRequest,
    db: Session = Depends(get_db)
):
    """
    API용 토큰 발급 엔드포인트 (JWT 토큰 발급)
    
    프론트엔드 애플리케이션에서 사용할 JWT 토큰을 발급받습니다.
    이 토큰을 사용하여 다른 API 엔드포인트에 인증할 수 있습니다.
    
    사용 예시:
    ```json
    POST /api/auth/token
    Content-Type: application/json
    
    {
        "username": "admin@example.com",
        "password": "password123"
    }
    ```
    
    응답:
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 86400
    }
    ```
    
    응답:
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "refresh-token-here...",
        "token_type": "bearer",
        "expires_in": 3600,
        "refresh_expires_in": 2592000
    }
    ```
    
    에러 응답 (401):
    ```json
    {
        "detail": "아이디 또는 비밀번호가 잘못되었습니다"
    }
    ```
    """
    ip = _get_client_ip(http_request)
    locked, msg = check_locked(db, token_request.username, ip)
    if locked:
        raise HTTPException(status_code=429, detail=msg, headers={"WWW-Authenticate": "Bearer"})

    user = db.query(models.AdminUser).filter(models.AdminUser.email == token_request.username).first()
    
    if not user or not utils.verify_password(token_request.password, user.hashed_password):
        record_failure(db, token_request.username, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 잘못되었습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    clear_attempts(db, token_request.username, ip)
    return _generate_token_response(user, db)


@router.post("/api/auth/login", response_model=TokenResponse)
async def api_login(
    http_request: Request,
    token_request: TokenRequest,
    db: Session = Depends(get_db)
):
    """
    API용 로그인 엔드포인트 (JWT 토큰 발급) - api_token과 동일
    """
    return await api_token(http_request, token_request, db)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/api/auth/refresh", response_model=TokenResponse)
async def api_refresh_token(
    body: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh Token으로 새 Access Token + 새 Refresh Token 발급 (로테이션)
    기존 Refresh Token은 무효화됨.
    """
    rt = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == body.refresh_token
    ).first()
    if not rt:
        raise HTTPException(status_code=401, detail="유효하지 않은 Refresh Token입니다.")
    now = datetime.utcnow()
    expires_naive = rt.expires_at.replace(tzinfo=None) if rt.expires_at.tzinfo else rt.expires_at
    if now > expires_naive:
        db.delete(rt)
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh Token이 만료되었습니다.")
    user = db.query(models.AdminUser).filter(models.AdminUser.id == rt.user_id).first()
    if not user:
        db.delete(rt)
        db.commit()
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    db.delete(rt)
    db.commit()
    return _generate_token_response(user, db)


@router.post("/api/auth/logout")
async def api_logout(body: LogoutRequest, db: Session = Depends(get_db)):
    """
    Refresh Token 블랙리스트 - DB에서 삭제하여 무효화
    """
    db.query(models.RefreshToken).filter(
        models.RefreshToken.token == body.refresh_token
    ).delete()
    db.commit()
    return {"success": True, "message": "로그아웃되었습니다."}


@router.post("/api/auth/social-login", response_model=SocialLoginResponse)
async def api_social_login(
    social_request: SocialLoginRequest,
    db: Session = Depends(get_db)
):
    """
    소셜 로그인 회원 등록 API 엔드포인트
    
    구글 소셜 로그인을 통해 인증된 사용자 정보를 받아
    일반 회원(Member) 테이블에 저장하거나 업데이트합니다.
    관리자 계정(AdminUser)과는 별개로 관리됩니다.
    
    사용 예시:
    ```json
    POST /api/auth/social-login
    Content-Type: application/json
    
    {
        "provider": "google",
        "email": "user@example.com",
        "name": "홍길동",
        "provider_id": "1234567890"
    }
    ```
    
    응답:
    ```json
    {
        "success": true,
        "message": "회원 정보가 저장되었습니다.",
        "member_id": 1
    }
    ```
    
    에러 응답 (400):
    ```json
    {
        "success": false,
        "message": "유효하지 않은 provider입니다. 'google'만 허용됩니다."
    }
    ```
    """
    # Provider 검증 (카카오·네이버 소셜 로그인 비활성화 — 기존: ['google', 'naver'])
    if social_request.provider not in ['google']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 provider입니다. 'google'만 허용됩니다."
        )
    
    # 이메일 또는 provider_id로 기존 회원 찾기
    from sqlalchemy import or_, and_
    existing_member = db.query(models.Member).filter(
        or_(
            models.Member.email == social_request.email,
            and_(
                models.Member.provider == social_request.provider,
                models.Member.provider_id == social_request.provider_id
            )
        )
    ).first()
    
    if existing_member:
        # 기존 회원: 정보 업데이트 (이름, provider 정보)
        existing_member.name = social_request.name
        existing_member.provider = social_request.provider
        existing_member.provider_id = social_request.provider_id
        # 이메일이 다른 경우 업데이트 (provider_id로 찾은 경우)
        if existing_member.email != social_request.email:
            existing_member.email = social_request.email
        db.commit()
        db.refresh(existing_member)
        grant_daily_login_bonus(db, existing_member)
        db.refresh(existing_member)
        return SocialLoginResponse(
            success=True,
            message="회원 정보가 업데이트되었습니다.",
            member_id=existing_member.id,
            has_nickname=bool(existing_member.nickname),
            nickname=existing_member.nickname,
            profile_image=existing_member.profile_image,
            grade=get_effective_grade(existing_member),
            access_token=utils.create_access_token(data={"sub": existing_member.email, "type": "member"}),
            point_balance=int(existing_member.point_balance or 0),
        )
    else:
        # 신규 회원: 자동 프로필 생성 (데이터베이스 기반)
        profile = generate_profile(db)

        new_member = models.Member(
            email=social_request.email,
            name=profile["name"],  # 캐릭터 이름
            nickname=profile["nickname"],  # 자동 생성된 닉네임
            profile_image=profile["profile_image"],  # 캐릭터 프로필 이미지
            provider=social_request.provider,
            provider_id=social_request.provider_id,
            status="active"
        )
        db.add(new_member)
        db.commit()
        db.refresh(new_member)
        grant_signup_bonus(db, new_member)
        grant_daily_login_bonus(db, new_member)
        db.refresh(new_member)
        return SocialLoginResponse(
            success=True,
            message="회원 정보가 저장되었습니다.",
            member_id=new_member.id,
            has_nickname=bool(new_member.nickname),
            nickname=new_member.nickname,
            profile_image=new_member.profile_image,
            grade=get_effective_grade(new_member),
            access_token=utils.create_access_token(data={"sub": new_member.email, "type": "member"}),
            point_balance=int(new_member.point_balance or 0),
        )


@router.put("/api/auth/member/update", response_model=SocialLoginResponse)
async def api_update_member(
    update_request: UpdateMemberRequest,
    db: Session = Depends(get_db)
):
    """
    회원 정보 업데이트 API 엔드포인트
    
    회원가입 페이지에서 설정한 닉네임과 프로필 이미지를 업데이트합니다.
    
    사용 예시:
    ```json
    PUT /api/auth/member/update
    Content-Type: application/json
    
    {
        "email": "user@example.com",
        "nickname": "홍길동",
        "profile_image": "data:image/jpeg;base64,..."
    }
    ```
    
    응답:
    ```json
    {
        "success": true,
        "message": "회원 정보가 업데이트되었습니다.",
        "member_id": 1
    }
    ```
    """
    # 이메일로 회원 찾기
    member = db.query(models.Member).filter(models.Member.email == update_request.email).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회원을 찾을 수 없습니다."
        )
    
    # 회원 정보 업데이트
    member.nickname = update_request.nickname
    if update_request.profile_image:
        member.profile_image = update_request.profile_image
    db.commit()
    db.refresh(member)

    return SocialLoginResponse(
        success=True,
        message="회원 정보가 업데이트되었습니다.",
        member_id=member.id,
        has_nickname=bool(member.nickname),
        nickname=member.nickname,
        profile_image=member.profile_image,
        grade=get_effective_grade(member),
        point_balance=int(member.point_balance or 0),
    )


@router.put("/api/auth/member/jubti")
async def api_update_member_jubti(
    request: JubtiUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    회원 주BTI(투자 성향) 저장 API
    """
    member = db.query(models.Member).filter(models.Member.email == request.email).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회원을 찾을 수 없습니다."
        )
    had_jubti = bool(member.jubti_type)
    member.jubti_type = request.jubti_type
    db.commit()
    db.refresh(member)
    if not had_jubti:
        grant_jubti_first_bonus(db, member)
        db.refresh(member)
    return {
        "success": True,
        "message": "주BTI 성향이 저장되었습니다.",
        "jubti_type": member.jubti_type,
        "point_balance": int(member.point_balance or 0),
    }


@router.get("/api/auth/member/jubti")
async def api_get_member_jubti(
    email: str,
    db: Session = Depends(get_db)
):
    """회원 주BTI(투자 성향) 조회 API"""
    member = db.query(models.Member).filter(models.Member.email == email).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="회원을 찾을 수 없습니다.")
    return {"success": True, "jubti_type": member.jubti_type}


@router.put("/api/auth/member/mbti")
async def api_update_member_mbti(
    request: MbtiUpdateRequest,
    db: Session = Depends(get_db)
):
    """회원 MBTI 저장 API (최초 입력 시 +50P)"""
    member = db.query(models.Member).filter(models.Member.email == request.email).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="회원을 찾을 수 없습니다.")
    had_mbti = bool(member.mbti_type)
    member.mbti_type = request.mbti_type
    db.commit()
    db.refresh(member)
    if not had_mbti:
        grant_mbti_first_bonus(db, member)
        db.refresh(member)
    return {
        "success": True,
        "mbti_type": member.mbti_type,
        "point_balance": int(member.point_balance or 0),
    }


@router.get("/api/auth/member/mbti")
async def api_get_member_mbti(
    email: str,
    db: Session = Depends(get_db)
):
    """회원 MBTI 조회 API"""
    member = db.query(models.Member).filter(models.Member.email == email).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="회원을 찾을 수 없습니다.")
    return {"success": True, "mbti_type": member.mbti_type}


@router.put("/api/auth/member/zodiac")
async def api_update_member_zodiac(
    request: ZodiacUpdateRequest,
    db: Session = Depends(get_db)
):
    """회원 띠/별자리 저장 API (각 최초 입력 시 +30P)"""
    if request.zodiac_animal is None and request.zodiac_sign is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="zodiac_animal 또는 zodiac_sign 중 하나는 필수입니다.")
    member = db.query(models.Member).filter(models.Member.email == request.email).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="회원을 찾을 수 없습니다.")
    had_animal = bool(member.zodiac_animal)
    had_sign = bool(member.zodiac_sign)
    if request.zodiac_animal is not None:
        member.zodiac_animal = request.zodiac_animal
    if request.zodiac_sign is not None:
        member.zodiac_sign = request.zodiac_sign
    db.commit()
    db.refresh(member)
    if not had_animal and member.zodiac_animal:
        grant_zodiac_animal_first_bonus(db, member)
        db.refresh(member)
    if not had_sign and member.zodiac_sign:
        grant_zodiac_sign_first_bonus(db, member)
        db.refresh(member)
    return {
        "success": True,
        "zodiac_animal": member.zodiac_animal,
        "zodiac_sign": member.zodiac_sign,
        "point_balance": int(member.point_balance or 0),
    }


@router.get("/api/auth/member/zodiac")
async def api_get_member_zodiac(
    email: str,
    db: Session = Depends(get_db)
):
    """회원 띠/별자리 조회 API"""
    member = db.query(models.Member).filter(models.Member.email == email).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="회원을 찾을 수 없습니다.")
    return {"success": True, "zodiac_animal": member.zodiac_animal, "zodiac_sign": member.zodiac_sign}


@router.get("/api/auth/member/info", response_model=SocialLoginResponse)
async def api_get_member_info(
    email: str,
    db: Session = Depends(get_db)
):
    """
    회원 정보 조회 API 엔드포인트
    
    이메일로 회원 정보를 조회합니다.
    
    사용 예시:
    GET /api/auth/member/info?email=user@example.com
    
    응답:
    ```json
    {
        "success": true,
        "message": "회원 정보를 조회했습니다.",
        "member_id": 1,
        "has_nickname": true,
        "nickname": "홍길동",
        "profile_image": "https://..."
    }
    ```
    """
    # 이메일로 회원 찾기
    member = db.query(models.Member).filter(models.Member.email == email).first()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회원을 찾을 수 없습니다."
        )

    # 세션 유지 상태에서도 일일 접속 포인트 적립 (중복 방지 로직 내장)
    grant_daily_login_bonus(db, member)
    db.refresh(member)

    return SocialLoginResponse(
        success=True,
        message="회원 정보를 조회했습니다.",
        member_id=member.id,
        has_nickname=bool(member.nickname),
        nickname=member.nickname,
        profile_image=member.profile_image,
        grade=get_effective_grade(member),
        point_balance=int(member.point_balance or 0),
    )


@router.post("/api/auth/member/screening-pick/charge")
async def api_screening_pick_charge(
    body: ScreeningPickChargeRequest,
    db: Session = Depends(get_db),
):
    """스크리닝 표 담기: 무료 순위 초과 시 20P 차감(Family·무료 구간 제외)"""
    st = (body.screening_type or "").strip().lower()
    if st not in ("ichimoku", "jongbe", "ricebowl", "breakout"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="screening_type은 ichimoku, jongbe, ricebowl, breakout 중 하나여야 합니다.",
        )
    email = (body.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이메일이 필요합니다.")
    member = db.query(models.Member).filter(models.Member.email == email).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="회원을 찾을 수 없습니다.")
    ok, did_charge, err = charge_screening_pick_if_needed(
        db,
        member,
        rank=int(body.rank),
        stock_code=(body.stock_code or "").strip(),
        screening_date=(body.screening_date or "").strip(),
        screening_type=st,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err or "포인트가 부족합니다.",
        )
    db.refresh(member)
    return {
        "success": True,
        "charged": did_charge,
        "point_balance": int(member.point_balance or 0),
    }


@router.get("/api/auth/member/favorites", response_model=FavoriteStockResponse)
async def api_get_favorite_stocks(
    email: str,
    db: Session = Depends(get_db)
):
    """
    관심종목 조회 API 엔드포인트
    
    회원의 관심종목 목록을 조회합니다.
    
    사용 예시:
    GET /api/auth/member/favorites?email=user@example.com
    
    응답:
    ```json
    {
        "success": true,
        "message": "관심종목 목록을 조회했습니다.",
        "favorite_stocks": ["005930", "035720", "000660"]
    }
    ```
    """
    import json
    
    # 이메일로 회원 찾기
    member = db.query(models.Member).filter(models.Member.email == email).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회원을 찾을 수 없습니다."
        )
    
    # 관심종목 목록 파싱
    favorite_stocks = []
    if member.favorite_stocks:
        try:
            favorite_stocks = json.loads(member.favorite_stocks)
            if not isinstance(favorite_stocks, list):
                favorite_stocks = []
        except (json.JSONDecodeError, TypeError):
            favorite_stocks = []
    
    return FavoriteStockResponse(
        success=True,
        message="관심종목 목록을 조회했습니다.",
        favorite_stocks=favorite_stocks
    )


@router.post("/api/auth/member/favorites", response_model=FavoriteStockResponse)
async def api_add_favorite_stock(
    favorite_request: FavoriteStockRequest,
    db: Session = Depends(get_db)
):
    """
    관심종목 추가 API 엔드포인트
    
    회원의 관심종목을 추가합니다. (일반 회원 6개, VIP 등급 이상 16개)
    
    사용 예시:
    ```json
    POST /api/auth/member/favorites
    Content-Type: application/json
    
    {
        "email": "user@example.com",
        "stock_code": "005930"
    }
    ```
    
    응답:
    ```json
    {
        "success": true,
        "message": "관심종목이 추가되었습니다.",
        "favorite_stocks": ["005930", "035720"]
    }
    ```
    """
    import json
    
    # 이메일로 회원 찾기
    member = db.query(models.Member).filter(models.Member.email == favorite_request.email).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회원을 찾을 수 없습니다."
        )
    
    # 관심종목 목록 파싱
    favorite_stocks = []
    if member.favorite_stocks:
        try:
            favorite_stocks = json.loads(member.favorite_stocks)
            if not isinstance(favorite_stocks, list):
                favorite_stocks = []
        except (json.JSONDecodeError, TypeError):
            favorite_stocks = []
    
    # 이미 추가되어 있는지 확인
    if favorite_request.stock_code in favorite_stocks:
        return FavoriteStockResponse(
            success=True,
            message="이미 등록된 관심종목입니다.",
            favorite_stocks=favorite_stocks
        )
    
    # 등급별 최대 개수 제한 확인 (일반 6개, VIP 이상 16개)
    effective_grade = get_effective_grade(member)
    max_count = 16 if effective_grade in ("vip", "family") else 6
    if len(favorite_stocks) >= max_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"최대 {max_count}개 종목까지만 등록할 수 있습니다."
        )
    
    # 관심종목 추가
    favorite_stocks.append(favorite_request.stock_code)
    member.favorite_stocks = json.dumps(favorite_stocks, ensure_ascii=False)
    db.commit()
    db.refresh(member)
    
    return FavoriteStockResponse(
        success=True,
        message="관심종목이 추가되었습니다.",
        favorite_stocks=favorite_stocks
    )


@router.delete("/api/auth/member/favorites", response_model=FavoriteStockResponse)
async def api_remove_favorite_stock(
    favorite_request: FavoriteStockRequest,
    db: Session = Depends(get_db)
):
    """
    관심종목 삭제 API 엔드포인트
    
    회원의 관심종목을 삭제합니다.
    
    사용 예시:
    ```json
    DELETE /api/auth/member/favorites
    Content-Type: application/json
    
    {
        "email": "user@example.com",
        "stock_code": "005930"
    }
    ```
    
    응답:
    ```json
    {
        "success": true,
        "message": "관심종목이 삭제되었습니다.",
        "favorite_stocks": ["035720", "000660"]
    }
    ```
    """
    import json
    
    # 이메일로 회원 찾기
    member = db.query(models.Member).filter(models.Member.email == favorite_request.email).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회원을 찾을 수 없습니다."
        )
    
    # 관심종목 목록 파싱
    favorite_stocks = []
    if member.favorite_stocks:
        try:
            favorite_stocks = json.loads(member.favorite_stocks)
            if not isinstance(favorite_stocks, list):
                favorite_stocks = []
        except (json.JSONDecodeError, TypeError):
            favorite_stocks = []
    
    # 관심종목 삭제
    if favorite_request.stock_code in favorite_stocks:
        favorite_stocks.remove(favorite_request.stock_code)
        member.favorite_stocks = json.dumps(favorite_stocks, ensure_ascii=False) if favorite_stocks else None
        db.commit()
        db.refresh(member)
        
        return FavoriteStockResponse(
            success=True,
            message="관심종목이 삭제되었습니다.",
            favorite_stocks=favorite_stocks
        )
    else:
        return FavoriteStockResponse(
            success=True,
            message="등록되지 않은 관심종목입니다.",
            favorite_stocks=favorite_stocks
        )


@router.delete("/api/auth/member/withdraw")
async def api_withdraw_member(
    email: str,
    db: Session = Depends(get_db)
):
    """
    회원 탈퇴 API 엔드포인트
    
    회원 정보를 데이터베이스에서 삭제합니다.
    
    사용 예시:
    DELETE /api/auth/member/withdraw?email=user@example.com
    
    응답:
    ```json
    {
        "success": true,
        "message": "회원 탈퇴가 완료되었습니다."
    }
    ```
    """
    # 이메일로 회원 찾기
    member = db.query(models.Member).filter(models.Member.email == email).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회원을 찾을 수 없습니다."
        )
    
    try:
        # 회원 삭제
        db.delete(member)
        db.commit()
        
        return {
            "success": True,
            "message": "회원 탈퇴가 완료되었습니다."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"회원 탈퇴 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/api/auth/characters", response_model=CharactersResponse)
async def api_get_characters(db: Session = Depends(get_db)):
    """
    캐릭터 목록 조회 API 엔드포인트
    
    회원가입 시 선택할 수 있는 캐릭터 목록을 조회합니다.
    
    사용 예시:
    GET /api/auth/characters
    
    응답:
    ```json
    {
        "success": true,
        "message": "캐릭터 목록을 조회했습니다.",
        "characters": [
            {"name": "🐂 황소", "image": "/image/characters/bull.png"},
            {"name": "🐻 곰", "image": "/image/characters/bear.png"}
        ]
    }
    ```
    """
    from app.utils.profile_generator import get_all_characters_from_db
    
    characters = get_all_characters_from_db(db)
    character_list = [
        CharacterInfo(name=char["name"], image=char["image"])
        for char in characters
    ]
    
    return CharactersResponse(
        success=True,
        message="캐릭터 목록을 조회했습니다.",
        characters=character_list
    )


@router.get("/api/auth/stock-words")
async def api_get_stock_words(db: Session = Depends(get_db)):
    """
    주식 관련 단어 목록 조회 API 엔드포인트
    
    닉네임 생성에 사용할 주식 관련 단어 목록을 조회합니다.
    
    사용 예시:
    GET /api/auth/stock-words
    
    응답:
    ```json
    {
        "success": true,
        "message": "주식 단어 목록을 조회했습니다.",
        "words": ["투자자", "트레이더", "분석가", ...]
    }
    ```
    """
    from pydantic import BaseModel
    
    class StockWordsResponse(BaseModel):
        success: bool
        message: str
        words: list[str]
    
    from app.utils.profile_generator import get_all_stock_words_from_db
    
    words = get_all_stock_words_from_db(db)
    
    if not words:
        words = ["투자자"]  # 기본값
    
    return StockWordsResponse(
        success=True,
        message="주식 단어 목록을 조회했습니다.",
        words=words
    )


@router.get("/api/auth/generate-nickname")
async def api_generate_nickname(db: Session = Depends(get_db)):
    """
    랜덤 닉네임 생성 API 엔드포인트
    
    회원가입 시 사용할 랜덤 닉네임을 생성합니다.
    
    사용 예시:
    GET /api/auth/generate-nickname
    
    응답:
    ```json
    {
        "success": true,
        "message": "닉네임이 생성되었습니다.",
        "nickname": "투자자123456"
    }
    ```
    """
    from pydantic import BaseModel
    from app.utils.profile_generator import generate_random_nickname
    
    class NicknameResponse(BaseModel):
        success: bool
        message: str
        nickname: str
    
    nickname = generate_random_nickname(db)

    return NicknameResponse(
        success=True,
        message="닉네임이 생성되었습니다.",
        nickname=nickname
    )


@router.get("/api/auth/check-email")
@limiter.limit("20/minute")
async def api_check_email(request: Request, email: str, db: Session = Depends(get_db)):
    """
    이메일 중복 확인 API 엔드포인트

    사용 예시:
    GET /api/auth/check-email?email=test@example.com

    응답:
    {"success": true, "available": true, "message": "사용 가능한 이메일입니다."}
    {"success": true, "available": false, "message": "이미 가입된 이메일입니다."}
    """
    existing = db.query(models.Member).filter(
        models.Member.email == email
    ).first()

    if existing:
        return {
            "success": True,
            "available": False,
            "message": "이미 가입된 이메일입니다."
        }

    return {
        "success": True,
        "available": True,
        "message": "사용 가능한 이메일입니다."
    }


@router.post("/api/auth/member/signup", response_model=MemberLoginResponse)
@limiter.limit("10/minute")
async def api_member_signup(
    request: Request,
    signup_request: MemberSignupRequest,
    db: Session = Depends(get_db)
):
    """
    일반 회원가입 API 엔드포인트 (이메일/비밀번호)

    닉네임은 BO 프로필 관리의 StockWord에서 랜덤 생성하고,
    프로필 이미지는 BO 캐릭터에서 랜덤 배정합니다.
    """
    # 이메일 중복 확인
    existing = db.query(models.Member).filter(
        models.Member.email == signup_request.email
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 가입된 이메일입니다."
        )

    try:
        # 프로필 자동 생성 (캐릭터 이미지 + 닉네임)
        profile = generate_profile(db)

        # 프론트에서 전달한 닉네임이 있으면 사용, 없으면 서버 생성 닉네임 사용
        final_nickname = signup_request.nickname if signup_request.nickname else profile["nickname"]

        # 비밀번호 해시화
        hashed_pw = utils.get_password_hash(signup_request.password)

        # 사용자가 이름을 입력했으면 사용, 없으면 프로필 자동 생성 이름 사용
        final_name = signup_request.name.strip() if signup_request.name and signup_request.name.strip() else profile["name"]

        new_member = models.Member(
            email=signup_request.email,
            name=final_name,
            nickname=final_nickname,
            hashed_password=hashed_pw,
            profile_image=profile["profile_image"],
            provider="email",
            provider_id=None,
            status="active"
        )
        db.add(new_member)
        db.commit()
        db.refresh(new_member)
        grant_signup_bonus(db, new_member)
        db.refresh(new_member)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ 회원가입 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"회원가입 처리 중 오류가 발생했습니다: {str(e)}"
        )

    return MemberLoginResponse(
        success=True,
        message="회원가입이 완료되었습니다.",
        member_id=new_member.id,
        email=new_member.email,
        nickname=new_member.nickname,
        profile_image=new_member.profile_image,
        grade=get_effective_grade(new_member),
        point_balance=int(new_member.point_balance or 0),
    )


@router.post("/api/auth/member/login", response_model=MemberLoginResponse)
@limiter.limit("10/minute")
async def api_member_login(
    request: Request,
    login_request: MemberLoginRequest,
    db: Session = Depends(get_db)
):
    """
    일반 회원 로그인 API 엔드포인트 (이메일/비밀번호)
    """
    ip = _get_client_ip(request)
    locked, msg = check_locked(db, login_request.email, ip)
    if locked:
        raise HTTPException(status_code=429, detail=msg)

    member = db.query(models.Member).filter(
        models.Member.email == login_request.email
    ).first()

    if not member:
        record_failure(db, login_request.email, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 잘못되었습니다."
        )

    # 소셜 로그인 사용자인 경우 (비밀번호 없음)
    if not member.hashed_password:
        record_failure(db, login_request.email, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="소셜 로그인으로 가입된 계정입니다. 소셜 로그인을 이용해주세요."
        )

    if not utils.verify_password(login_request.password, member.hashed_password):
        record_failure(db, login_request.email, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 잘못되었습니다."
        )

    clear_attempts(db, login_request.email, ip)

    grant_daily_login_bonus(db, member)
    db.refresh(member)
    access_token = utils.create_access_token(data={"sub": member.email, "type": "member"})
    return MemberLoginResponse(
        success=True,
        message="로그인 성공",
        member_id=member.id,
        email=member.email,
        nickname=member.nickname,
        profile_image=member.profile_image,
        grade=get_effective_grade(member),
        access_token=access_token,
        point_balance=int(member.point_balance or 0),
    )


# 아이디(이메일) 찾기 요청 모델
class FindEmailRequest(BaseModel):
    name: str  # 이름으로 검색


# 아이디(이메일) 찾기 - 비밀번호 확인으로 전체 이메일 조회
class VerifyEmailRequest(BaseModel):
    password: str
    name: str  # 검색에 사용한 이름


# 비밀번호 재설정 요청 모델
class RequestPasswordResetRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    name: str  # 본인 확인용 이름
    new_password: str


def _mask_email(email: str) -> str:
    """이메일 마스킹 (예: h***a@gmail.com)"""
    if not email or "@" not in email:
        return "***@***.***"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


@router.post("/api/auth/member/find-email")
async def api_find_email(
    request: FindEmailRequest,
    db: Session = Depends(get_db)
):
    """
    아이디(이메일) 찾기 - 이름으로 가입된 이메일 목록 조회 (일반 회원만, 마스킹 처리)
    """
    search_name = request.name.strip()
    if not search_name:
        return {"success": False, "message": "이름을 입력해주세요."}

    members = db.query(models.Member).filter(
        models.Member.name == search_name,
        models.Member.hashed_password.isnot(None),
        models.Member.status == "active"
    ).all()

    emails = [_mask_email(m.email) for m in members]
    return {"success": True, "emails": emails}


@router.post("/api/auth/member/verify-email")
async def api_verify_email(
    request: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    아이디(이메일) 찾기 - 비밀번호 확인 후 전체 이메일 표시
    """
    search_name = request.name.strip()
    if not search_name or not request.password:
        return {"success": False, "message": "이름과 비밀번호를 입력해주세요."}

    # 이름으로 검색된 회원 중 비밀번호가 일치하는 회원의 전체 이메일 반환
    members = db.query(models.Member).filter(
        models.Member.name == search_name,
        models.Member.hashed_password.isnot(None),
        models.Member.status == "active"
    ).all()

    verified_emails = []
    for m in members:
        if utils.verify_password(request.password, m.hashed_password):
            verified_emails.append(m.email)

    if not verified_emails:
        return {"success": False, "message": "비밀번호가 일치하는 계정이 없습니다."}

    return {"success": True, "emails": verified_emails}


def _send_password_reset_email(to_email: str, code: str) -> bool:
    """Resend로 비밀번호 재설정 인증코드 이메일 발송. 성공 시 True, 실패 시 False."""
    if not RESEND_API_KEY:
        return False
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        html = f"""
        <p>플로우 비밀번호 재설정 인증코드입니다.</p>
        <p><strong>{code}</strong></p>
        <p>이 코드는 10분간 유효합니다.</p>
        <p>본인이 요청하지 않았다면 이 메일을 무시해 주세요.</p>
        """
        resend.Emails.send({
            "from": PASSWORD_RESET_FROM_EMAIL,
            "to": [to_email],
            "subject": "[플로우] 비밀번호 재설정 인증코드",
            "html": html,
        })
        return True
    except Exception as e:
        safe_log_error("비밀번호 재설정 이메일 발송", e)
        return False


@router.post("/api/auth/member/request-password-reset")
@limiter.limit("5/minute")
async def api_request_password_reset(
    http_request: Request,
    request: RequestPasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    비밀번호 재설정 1단계 - 이메일 존재 확인 + 이름 힌트 제공
    """
    member = db.query(models.Member).filter(
        models.Member.email == request.email.strip().lower(),
        models.Member.hashed_password.isnot(None),
        models.Member.status == "active"
    ).first()

    if not member:
        return {"success": False, "message": "등록되지 않은 이메일입니다."}

    # 이름 마스킹 힌트 제공 (예: "홍*동")
    name = member.name or ""
    if len(name) <= 1:
        masked_name = "*"
    elif len(name) == 2:
        masked_name = name[0] + "*"
    else:
        masked_name = name[0] + "*" * (len(name) - 2) + name[-1]

    return {
        "success": True,
        "message": "이메일이 확인되었습니다. 이름을 입력해주세요.",
        "name_hint": masked_name,
    }


@router.post("/api/auth/member/reset-password")
@limiter.limit("10/minute")
async def api_reset_password(
    http_request: Request,
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    비밀번호 재설정 2단계 - 이메일 + 이름 확인 후 새 비밀번호로 변경
    """
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비밀번호는 8자 이상이어야 합니다."
        )

    member = db.query(models.Member).filter(
        models.Member.email == request.email.strip().lower(),
        models.Member.hashed_password.isnot(None),
        models.Member.status == "active"
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")

    # 이름 확인으로 본인 인증
    if (member.name or "").strip() != (request.name or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이름이 일치하지 않습니다."
        )

    member.hashed_password = utils.get_password_hash(request.new_password)
    db.commit()

    return {"success": True, "message": "비밀번호가 변경되었습니다."}


class ReissueTokenRequest(BaseModel):
    email: str


@router.post("/api/auth/member/reissue-token")
async def reissue_member_token(
    body: ReissueTokenRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    db: Session = Depends(get_db),
):
    """
    회원 JWT 액세스 토큰 재발급 (X-API-KEY 인증 필요)
    NextAuth 세션에 저장된 backendAccessToken이 만료될 때 자동 갱신에 사용됩니다.
    """
    if not x_api_key or x_api_key.strip() != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    member = db.query(models.Member).filter(
        models.Member.email == body.email,
        models.Member.status == "active",
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = utils.create_access_token(data={"sub": member.email, "type": "member"})
    return {"success": True, "access_token": access_token}


@router.get("/api/auth/random-profile-image")
async def api_random_profile_image(db: Session = Depends(get_db)):
    """
    프로필 관리의 캐릭터 이미지 중 랜덤으로 하나를 반환합니다.
    설정 > 프로필 수정에서 랜덤 프로필 이미지를 보여줄 때 사용합니다.
    """
    from app.utils.profile_generator import generate_random_character

    character = generate_random_character(db)

    return {
        "success": True,
        "message": "랜덤 프로필 이미지가 생성되었습니다.",
        "name": character["name"],
        "image": character["image"]
    }

