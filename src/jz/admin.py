"""Small, dependency-free administration console for the billing service."""

import base64
import binascii
import hashlib
import hmac
import time
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import settings
from .models import Bill, Borrower, User


router = APIRouter(prefix="/admin", tags=["管理员"])
COOKIE_NAME = "bill_admin_session"
ADMIN_PAGE = Path(__file__).with_name("admin.html")


class LoginRequest(BaseModel):
    username: str
    password: str


class BorrowerUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=8)


class BillUpdate(BaseModel):
    value: float = Field(allow_inf_nan=False)
    date: date


def _admin_enabled() -> bool:
    return bool(
        settings.admin_username
        and settings.admin_password
        and settings.admin_session_secret
    )


def _sign_session(expires_at: int) -> str:
    payload = f"{settings.admin_username}:{expires_at}".encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(
        settings.admin_session_secret.encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{signature}"


def _valid_session(token: str | None) -> bool:
    if not token or not _admin_enabled():
        return False
    try:
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(
            settings.admin_session_secret.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        padded = encoded + "=" * (-len(encoded) % 4)
        username, expires_at = base64.urlsafe_b64decode(padded).decode().rsplit(":", 1)
        return hmac.compare_digest(username, settings.admin_username) and int(expires_at) > time.time()
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return False


async def require_admin(
    bill_admin_session: str | None = Cookie(default=None),
) -> None:
    if not _valid_session(bill_admin_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")


async def _recalculate_totals(user_id: int, borrower_id: int | None = None) -> None:
    user_values = await Bill.filter(owner_id=user_id).values_list("value", flat=True)
    await User.filter(id=user_id).update(total_value=sum(user_values))
    if borrower_id is not None:
        borrower_values = await Bill.filter(borrower_id=borrower_id).values_list("value", flat=True)
        await Borrower.filter(id=borrower_id).update(total_value=sum(borrower_values))


@router.get("", include_in_schema=False)
async def admin_page():
    return FileResponse(ADMIN_PAGE)


@router.post("/api/login")
async def login(payload: LoginRequest, response: Response):
    if not _admin_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="管理员后台尚未配置，请设置 ADMIN_USERNAME、ADMIN_PASSWORD 和 ADMIN_SESSION_SECRET",
        )
    username_ok = hmac.compare_digest(payload.username, settings.admin_username)
    password_ok = hmac.compare_digest(payload.password, settings.admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    max_age = settings.admin_session_hours * 3600
    response.set_cookie(
        COOKIE_NAME,
        _sign_session(int(time.time()) + max_age),
        max_age=max_age,
        httponly=True,
        samesite="strict",
        secure=settings.admin_cookie_secure,
        path="/admin",
    )
    return {"ok": True}


@router.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/admin")
    return {"ok": True}


@router.get("/api/overview", dependencies=[Depends(require_admin)])
async def overview():
    users = await User.all().order_by("-reg_time").limit(200)
    borrowers = await Borrower.all().prefetch_related("owner").order_by("-id").limit(300)
    bills = await Bill.all().prefetch_related("owner", "borrower").order_by("-date", "-created_at").limit(500)
    all_values = await Bill.all().values_list("value", flat=True)
    return {
        "stats": {
            "users": await User.all().count(),
            "borrowers": await Borrower.all().count(),
            "bills": await Bill.all().count(),
            "total_value": sum(all_values),
        },
        "users": [
            {
                "id": user.id,
                "openid": user.openid,
                "total_value": user.total_value,
                "reg_time": user.reg_time.isoformat(),
            }
            for user in users
        ],
        "borrowers": [
            {
                "id": borrower.id,
                "name": borrower.name,
                "total_value": borrower.total_value,
                "owner_id": borrower.owner_id,
                "owner_openid": borrower.owner.openid,
            }
            for borrower in borrowers
        ],
        "bills": [
            {
                "id": bill.id,
                "date": bill.date.isoformat(),
                "value": bill.value,
                "borrower_id": bill.borrower_id,
                "borrower_name": bill.borrower.name,
                "owner_id": bill.owner_id,
                "owner_openid": bill.owner.openid,
            }
            for bill in bills
        ],
    }


@router.patch("/api/borrowers/{borrower_id}", dependencies=[Depends(require_admin)])
async def update_borrower(borrower_id: int, payload: BorrowerUpdate):
    borrower = await Borrower.get_or_none(id=borrower_id)
    if borrower is None:
        raise HTTPException(status_code=404, detail="借款人不存在")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="姓名不能为空")
    duplicate = await Borrower.filter(owner_id=borrower.owner_id, name=name).exclude(id=borrower_id).exists()
    if duplicate:
        raise HTTPException(status_code=409, detail="该用户已有同名借款人")
    borrower.name = name
    await borrower.save(update_fields=["name"])
    return {"ok": True}


@router.delete("/api/borrowers/{borrower_id}", dependencies=[Depends(require_admin)])
async def delete_borrower(borrower_id: int):
    borrower = await Borrower.get_or_none(id=borrower_id)
    if borrower is None:
        raise HTTPException(status_code=404, detail="借款人不存在")
    if await Bill.filter(borrower_id=borrower_id).exists():
        raise HTTPException(status_code=409, detail="请先删除该借款人的账单")
    await borrower.delete()
    return {"ok": True}


@router.patch("/api/bills/{bill_id}", dependencies=[Depends(require_admin)])
async def update_bill(bill_id: int, payload: BillUpdate):
    bill = await Bill.get_or_none(id=bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="账单不存在")
    bill.value = payload.value
    bill.date = payload.date
    await bill.save(update_fields=["value", "date"])
    await _recalculate_totals(bill.owner_id, bill.borrower_id)
    return {"ok": True}


@router.delete("/api/bills/{bill_id}", dependencies=[Depends(require_admin)])
async def delete_bill(bill_id: int):
    bill = await Bill.get_or_none(id=bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="账单不存在")
    owner_id, borrower_id = bill.owner_id, bill.borrower_id
    await bill.delete()
    await _recalculate_totals(owner_id, borrower_id)
    return {"ok": True}


@router.delete("/api/users/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(user_id: int):
    user = await User.get_or_none(id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    await user.delete()
    return {"ok": True}
