from datetime import datetime

from pydantic import BaseModel, validator, constr

from .models import Bill_Pydantic, Borrower_Pydantic_List, Borrower_Pydantic, Bill_Pydantic_List, Borrower_Info_Pydantic


class GetBorrowerRes(BaseModel):
    name: str
    totalValue: float
    billList: Bill_Pydantic_List


class GetBillRes(BaseModel):
    totalValue: float
    billList: list[Bill_Pydantic]


class BorrowerListRes(BaseModel):
    indexList: list[str]
    borrowerIndex: dict[str, list[Borrower_Info_Pydantic]]
