from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    phone: int
    disabled: bool

    class Config:
        orm_mode = True

class Detail(BaseModel):
    id: int
    username: str
    email: str
    phone: int
    full_name: str
    disabled: bool
    hashed_password: str

    class Config:
        orm_mode = True
