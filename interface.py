from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import database
from schemas import Token, TokenData, User, Detail


# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

@app.on_event("startup")
async def start_db():
    async with database.engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)


def create_user(db: AsyncSession, detail: Detail):
    #hashed_password= pwd_context.hash(detail.password)
    db_cred = Detail(**detail.dict())                              #creating new user
    db.add(db_cred)
    db.commit()
    db.refresh(db_cred)
    return db_cred


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)        #check whether the password is present in the db


def get_password_hash(password):
    return pwd_context.hash(password)                                  #hashing the password


async def get_user(db: AsyncSession, username: str) -> database.User:
    result = await db.execute(select(database.User).filter_by(username=username))         #check whether the username is present in the db
    return result.scalars().first()


async def authenticate_user(db: AsyncSession, username: str, password: str) -> database.User:
    user = await get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):                                #check the username and password belongs to same user
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})                                                     #tokenization
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(db: AsyncSession = Depends(database.get_db), token: str = Depends(oauth2_scheme)) -> database.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except PyJWTError:
        raise credentials_exception
    user = await get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> database.User:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")         #check whether the user is active or not
    return current_user


@app.post("/token", response_model=Token)
async def login_for_access_token(db: AsyncSession = Depends(database.get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,                     #logging in
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user                                                             #show the details of the user who logged in

@app.post("/users/register/", response_model=Detail)
async def create_new_user(item: Detail, db:  AsyncSession = Depends(database.get_db)):    #posting the details of new user
    return create_user(db=db, detail=item)
