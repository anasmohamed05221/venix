from pydantic import BaseModel, EmailStr, field_validator, Field
from utils.validators import validate_password, validate_phone

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    password: str 
    phone_number: str = Field(examples=["+20xxxxxxxxxx"])
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, value):
        return validate_password(value)

    
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, value):
        return validate_phone(value)
    


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str

    @field_validator('code')
    @classmethod
    def validate_code(cls, value):
        if len(value)!=6:
            raise ValueError('must be a 6-digit code')
        return value


class RefreshTokenRequest(BaseModel):
    refresh_token: str
    
    @field_validator('refresh_token')
    @classmethod
    def validate_token(cls, value):
        if not value or not value.strip():
            raise ValueError('Refresh token cannot be empty')
        return value

class RevokeTokenRequest(BaseModel):
    refresh_token: str

    @field_validator('refresh_token')
    @classmethod
    def validate_token(cls, value):
        if not value or not value.strip():
            raise ValueError('Refresh token cannot be empty')
        return value

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, value):
        return validate_password(value)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr



class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, value):
        return validate_password(value)

class DeactivateUserRequest(BaseModel):
    password: str

