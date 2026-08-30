from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, status, Depends, APIRouter
from fastapi.security import APIKeyHeader
from tortoise.contrib.fastapi import register_tortoise
from tortoise.exceptions import DoesNotExist

from .admin import router as admin_router
from .config import Miniprogram as MiniprogramConfig, prepare_sqlite_directory, settings
from .miniprogram import Auth as MiniprogramAuth, Code2SessionRes, LoginInfo
from .models import User, Token, Borrower, Borrower_Pydantic, Borrower_In_Pydantic, \
    Bill_Pydantic_List, Bill, Bill_Pydantic, Auth, Borrower_Pydantic_List, Bill_In_Pydantic

token_in_herder = APIKeyHeader(name='token')

prepare_sqlite_directory()

app = FastAPI(title='记账助手后端', version='1.1')
api = APIRouter(prefix='/api')


async def get_current_user(token: str = Depends(token_in_herder)):
    auth_error = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="认证失败", )
    if not token:
        raise auth_error
    auth_obj = await Auth.get_or_none(token=token)
    if auth_obj is None or auth_obj.expire_time <= datetime.now().astimezone():
        raise auth_error
    return await auth_obj.owner


async def get_wx_user_info(code: str) -> Code2SessionRes:
    wx_user_info = await MiniprogramAuth.code2session(
        appid=MiniprogramConfig.appid,
        secret=MiniprogramConfig.secret,
        js_code=code
    )
    if wx_user_info.openid:
        return wx_user_info
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='获取用户信息失败'
        )


async def get_borrower(borrower_id: int, user: User = Depends(get_current_user)):
    try:
        return await Borrower.get(owner=user, id=borrower_id)
    except DoesNotExist:
        raise HTTPException(status_code=400, detail="借款人不存在")


@api.get("/")
async def index():
    return 'Hello api'


@app.get("/health", tags=["系统"])
async def health():
    return {"status": "ok"}


@api.post("/login", response_model=Token, tags=['认证'])
async def login_for_access_token(login_info: LoginInfo):
    wx_user_info = await get_wx_user_info(login_info.code)
    user, created = await User.get_or_create(openid=wx_user_info.openid)
    auth, _ = await Auth.get_or_create(owner=user)
    await auth.refresh()
    return await Token.from_tortoise_orm(auth)


@api.post("/refreshToken", response_model=Token, tags=['认证'])
async def post_refresh_token(user: User = Depends(get_current_user)):
    auth = await user.auth
    await auth.refresh()
    return await Token.from_tortoise_orm(auth)


@api.get('/totalValue', tags=['账单'])
async def get_user_total_value(user: User = Depends(get_current_user)):
    return user.total_value


@api.get('/bill', response_model=Bill_Pydantic_List, tags=['账单'])
async def get_bill_list(offset: int = 0, limit: int = 50, user: User = Depends(get_current_user)):
    return await Bill_Pydantic_List.from_queryset(
        Bill.filter(owner=user).offset(offset).limit(limit).order_by('-date', '-created_at'))


@api.post('/bill', response_model=Bill_Pydantic, tags=['账单'])
async def post_bill(bill: Bill_In_Pydantic, user: User = Depends(get_current_user)):
    try:
        borrower_obj = await Borrower.get(id=bill.borrower_id, owner=user)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="借款人不存在")
    bill_obj = await Bill.create(borrower=borrower_obj, date=bill.date, value=bill.value, owner=user)
    user.total_value += bill_obj.value
    await user.save()
    borrower_obj.total_value += bill_obj.value
    await borrower_obj.save()
    return Bill_Pydantic.from_orm(bill_obj)


@api.delete('/bill/{bill_id}', tags=['账单'])
async def delete_bill(bill_id, user: User = Depends(get_current_user)):
    try:
        bill_obj = await Bill.get(owner=user, id=bill_id)
        borrower_obj = await bill_obj.borrower
        await bill_obj.delete()
    except DoesNotExist:
        raise HTTPException(status_code=400, detail="账单不存在")
    user.total_value -= bill_obj.value
    await user.save()
    borrower_obj.total_value -= bill_obj.value
    await borrower_obj.save()
    return


@api.post('/borrower', response_model=Borrower_Pydantic, tags=['借款人'])
async def post_borrower(borrower: Borrower_In_Pydantic, user: User = Depends(get_current_user)):
    exist = await Borrower.exists(owner=user, name=borrower.name)
    if exist:
        raise HTTPException(status_code=400, detail="借款人姓名重复")
    else:
        borrower_obj = await Borrower.create(owner=user, name=borrower.name)
        return await Borrower_Pydantic.from_tortoise_orm(borrower_obj)


@api.get('/borrower', response_model=Borrower_Pydantic_List, tags=['借款人'])
async def get_borrower_list(user: User = Depends(get_current_user)):
    return await Borrower_Pydantic_List.from_queryset(Borrower.filter(owner=user))


@api.get('/borrower/{borrower_id}', response_model=Borrower_Pydantic, tags=['借款人'])
async def get_borrower(borrower_id, user: User = Depends(get_current_user)):
    try:
        borrower_obj = await Borrower.get(owner=user, id=borrower_id)
    except DoesNotExist:
        raise HTTPException(status_code=400, detail="借款人不存在")
    return await Borrower_Pydantic.from_tortoise_orm(borrower_obj)


#
#
# @app.put('/borrower/{borrower_id}', response_model=Borrower_Pydantic, tags=['借款人'])
# async def put_borrower(borrower: Borrower_In_Pydantic, borrower_obj: Borrower = Depends(get_borrower)):
#     """
#     编辑借款人
#     :param borrower_obj: 借款人对象
#     :param borrower:借款人信息
#     :return:借款人修改后的信息
#     """
#     borrower_obj.name = borrower.name
#     await borrower_obj.save()
#     return await Borrower_Pydantic.from_tortoise_orm(borrower_obj)
#
#
# @app.delete('/borrower/{borrower_id}', tags=['借款人'])
# async def delete_borrower(borrower_obj: Borrower = Depends(get_borrower)):
#     """ 删除借款人
#     :param borrower_obj: 借款人对象
#     :return:
#     """
#     await borrower_obj.delete()
#     return True
#
#

#
#

app.include_router(api)
app.include_router(admin_router)
register_tortoise(
    app,
    config={
        'connections': {
            'default': settings.database_url
        },
        'apps': {
            'models': {
                "models": ["jz.models"],
                'default_connection': 'default',
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    },
    generate_schemas=True,
    add_exception_handlers=True,
)

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8081, reload=True)
