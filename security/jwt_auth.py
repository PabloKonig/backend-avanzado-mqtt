from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Annotated
from fastapi import Depends, HTTPException, status
import jwt, os

# Configuración del JWT
SECRET_KEY = "CodigoFacilito!!!##&"
ALGORITHM = "HS256"                                                 # Algoritmo de encriptación de la firma del JWT.
ACCESS_TOKEN_EXPIRE_MINUTES = 30                                    # Tiempo de expiración del token

super_users_db = {
    "BackEnd Avanzado": {
        "username": os.environ.get("API_USERNAME"),
        "full_name": "Pablo Alexis König",
        "email": "pablokonig@yahoo.com",
        "hashed_password": os.environ.get("API_HASHED_PASSWORD"),
        "disabled": False,
    }
}
super_users_db = {
    "CodigoFacilito": {
        "username": "CodigoFacilito",
        "full_name": "Codigo Facilito",
        "email": "soporte@codigofacilito.com",
        "hashed_password": "$2b$12$GK3GH2GxbZsOsb3HyQVkS.5jhC/DkWsK42c0i0o.rKxotCj2PPihC",
        "disabled": False,
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

# Configuración de hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/token")     # Esquema de autorización OAuth2 y ruta para login.

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

# Función para crear el token de acceso JWT
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Función para autenticar al usuario
def authenticate_user(super_db, username: str, password: str):
    user = get_user(super_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
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
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(super_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

