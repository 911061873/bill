from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import constr
from tortoise import fields, Tortoise
from tortoise.contrib.pydantic import pydantic_model_creator, pydantic_queryset_creator
from tortoise.models import Model
from xpinyin import Pinyin

from .config import Auth as AuthConfig


class User(Model):
    id = fields.IntField(pk=True)
    openid = fields.CharField(max_length=255, index=True)
    reg_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)
    total_value = fields.FloatField(default=0)

    auth = fields.ReverseRelation['Auth']
    borrowers = fields.ReverseRelation['Borrower']
    bills = fields.ReverseRelation['Bill']

    class PydanticMeta:
        exclude = ('owner', 'owner_id')


class Auth(Model):
    id = fields.IntField(pk=True)
    token = fields.UUIDField(default=uuid4, index=True)
    expire_time = fields.DatetimeField(
        default=lambda: datetime.now().astimezone() + timedelta(hours=AuthConfig.token_expire_hour))
    owner = fields.OneToOneField('models.User', related_name='auth')

    async def refresh(self):
        self.expire_time = datetime.now().astimezone() + timedelta(hours=AuthConfig.token_expire_hour)
        await self.save()

    class PydanticMeta:
        include = ('token', 'expire_time')


class Borrower(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=8, index=True)
    owner = fields.ForeignKeyField('models.User', related_name='borrowers')
    total_value = fields.FloatField(default=0)

    bills = fields.ReverseRelation['Bill']

    class PydanticMeta:
        exclude = ('owner', 'owner_id')

    def pinyin(self) -> str:
        return Pinyin().get_initial(self.name[0])


class Bill(Model):
    id = fields.IntField(pk=True)
    borrower = fields.ForeignKeyField('models.Borrower', related_name='bills')
    date = fields.DateField()
    value = fields.FloatField()
    created_at = fields.DatetimeField(auto_now=True)
    owner = fields.ForeignKeyField('models.User', related_name='bills')

    class PydanticMeta:
        exclude = ('owner', 'owner_id', 'created_at')


Tortoise.init_models(["jz.models"], "models")

Token = pydantic_model_creator(Auth, name='Token')

Borrower_Pydantic = pydantic_model_creator(Borrower, name='Borrower')
Borrower_Info_Pydantic = pydantic_model_creator(Borrower, name='BorroweriInfo', exclude=('bills',))
Borrower_In_Pydantic = pydantic_model_creator(Borrower, name='BorrowerCreate', exclude_readonly=True)
Borrower_Pydantic_List = pydantic_queryset_creator(Borrower, exclude=('bills',), computed=('pinyin',))


Bill_Pydantic = pydantic_model_creator(Bill, name="Bill")
Bill_In_Pydantic = pydantic_model_creator(Bill, name='BillCreate', exclude_readonly=True)
# print(Bill_In_Pydantic.schema_json(indent=4))


# print(BillInPydantic.schema_json(indent=4))
Bill_Pydantic_List = pydantic_queryset_creator(Bill)
# print(Bill_Pydantic_List.schema_json(indent=4))
