"""
Authentication models and schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class AuthProvider(str, Enum):
    """Supported authentication providers"""
    GOOGLE = "google"
    FIREBASE = "firebase"
    LOCAL = "local"

class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: AuthProvider = AuthProvider.GOOGLE

class UserCreate(UserBase):
    """User creation model"""
    id: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class User(UserBase):
    """User model with all fields"""
    id: str
    created_at: datetime
    last_login: datetime
    preferences: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UserInDB(User):
    """User model as stored in database"""
    updated_at: Optional[datetime] = None

class Token(BaseModel):
    """JWT token response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

class TokenData(BaseModel):
    """Data encoded in JWT token"""
    sub: str  # user_id
    email: Optional[str] = None
    name: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None

class GoogleAuthRequest(BaseModel):
    """Google authentication request"""
    id_token: str  # Google ID token from frontend

class AuthResponse(BaseModel):
    """Authentication response"""
    user: User
    token: Token
    
class UserPreferences(BaseModel):
    """User preferences model"""
    synthesis_enabled: bool = True
    notification_enabled: bool = True
    timezone: str = "UTC"
    email_sync_enabled: bool = True
    calendar_sync_enabled: bool = True
    task_sync_enabled: bool = True
    synthesis_interval_minutes: int = 30
    daily_summary_time: Optional[str] = "09:00"  # HH:MM format
    
class UserSession(BaseModel):
    """User session information"""
    user_id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None