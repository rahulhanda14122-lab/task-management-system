from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Department, Role


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    department: Department
    experience_years: int = Field(ge=0, le=60)
    location: str
    role: Role = Role.USER


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
