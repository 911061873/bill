from typing import Optional

import httpx
from pydantic import BaseModel


class LoginInfo(BaseModel):
    code: str
    errMsg: str | None


class Code2SessionRes(BaseModel):
    openid: Optional[str] = None
    session_key: Optional[str] = None
    unionid: Optional[str] = None
    errcode: Optional[int] = None
    errmsg: Optional[str] = None

    def get_err_msg(self):
        msg_dict = {
            -1: '系统繁忙，此时请开发者稍候再试',
            0: '请求成功',
            40029: 'code 无效',
            45011: '频率限制，每个用户每分钟100次',
            40226: '高风险等级用户，小程序登录拦截 。风险等级详见用户安全解方案。',
        }
        return msg_dict.get(self.errcode, f'未知错误-{self.errcode}-{self.errmsg}')


class Auth:
    base_url = 'https://api.weixin.qq.com'
    client = httpx.Client(base_url=base_url)
    async_client = httpx.AsyncClient(base_url=base_url)

    @classmethod
    async def code2session(cls, appid: str, secret: str, js_code: str,
                           grant_type='authorization_code') -> Code2SessionRes:
        params = {
            'appid': appid,
            'secret': secret,
            'js_code': js_code,
            'grant_type': grant_type
        }
        if not appid or not secret:
            raise RuntimeError("WX_APPID and WX_SECRET must be configured")
        res = await cls.async_client.get(url='sns/jscode2session', params=params)
        res.raise_for_status()
        return Code2SessionRes.model_validate(res.json())
