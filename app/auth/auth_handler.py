"""
Authentication handler for JWT and OAuth logic
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.oauth2 import id_token
from google.auth.transport import requests

from app.config import settings
from app.database.firebase_client import firebase_client
from app.auth.models import (
    User, UserCreate, Token, TokenData, 
    GoogleAuthRequest, UserSession
)

logger = logging.getLogger(__name__)

# Security scheme for FastAPI
security = HTTPBearer()

class AuthHandler:
    """
    Handles authentication operations including JWT creation/verification
    and OAuth provider integration
    """
    
    def __init__(self):
        self.secret = settings.jwt_secret
        self.algorithm = settings.JWT_ALGORITHM
        self.expiration_minutes = settings.JWT_EXPIRATION_MINUTES
    
    def create_access_token(self, user_data: Dict[str, Any]) -> str:
        """
        Create a JWT access token
        
        Args:
            user_data: Dictionary containing user information
            
        Returns:
            Encoded JWT token
        """
        # Token payload
        payload = {
            'sub': user_data.get('id'),  # Subject (user ID)
            'email': user_data.get('email'),
            'name': user_data.get('name'),
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(minutes=self.expiration_minutes)
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Create token
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        
        logger.debug(f"Created token for user {payload.get('sub')}")
        return token
    
    def decode_token(self, token: str) -> Optional[TokenData]:
        """
        Decode and verify a JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            TokenData or None if invalid
        """
        try:
            payload = jwt.decode(
                token, 
                self.secret, 
                algorithms=[self.algorithm]
            )
            
            return TokenData(**payload)
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    async def verify_google_token(self, id_token_str: str) -> Optional[Dict[str, Any]]:
        """
        Verify a Google ID token
        
        Args:
            id_token_str: Google ID token from frontend
            
        Returns:
            User info from Google or None if invalid
        """
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
            
            # Verify issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                logger.error("Wrong issuer in Google token")
                return None
            
            # Extract user info
            user_info = {
                'id': idinfo['sub'],
                'email': idinfo.get('email'),
                'name': idinfo.get('name'),
                'picture': idinfo.get('picture'),
                'email_verified': idinfo.get('email_verified', False),
                'provider': 'google'
            }
            
            logger.info(f"Verified Google token for user {user_info['email']}")
            return user_info
            
        except ValueError as e:
            logger.error(f"Invalid Google token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying Google token: {e}")
            return None
    
    async def authenticate_google_user(self, auth_request: GoogleAuthRequest) -> Dict[str, Any]:
        """
        Authenticate a user with Google OAuth
        
        Args:
            auth_request: Google authentication request with ID token
            
        Returns:
            Dictionary with user and token information
        """
        # Verify Google token
        google_user = await self.verify_google_token(auth_request.id_token)
        if not google_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token"
            )
        
        # Ensure email is verified
        if not google_user.get('email_verified'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email not verified"
            )
        
        # Get or create user in Firebase
        user_data = firebase_client.get_or_create_user(google_user)
        
        # Create JWT token
        access_token = self.create_access_token(user_data)
        
        # Create response
        return {
            'user': User(**user_data),
            'token': Token(
                access_token=access_token,
                expires_in=self.expiration_minutes * 60
            )
        }
    
    async def get_current_user(
        self, 
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> UserSession:
        """
        Get the current authenticated user from JWT token
        
        Args:
            credentials: Bearer token from request header
            
        Returns:
            Current user session
            
        Raises:
            HTTPException: If token is invalid or user not found
        """
        token = credentials.credentials
        
        # Decode token
        token_data = self.decode_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from database
        user = firebase_client.get_user(token_data.sub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create session
        return UserSession(
            user_id=user['id'],
            email=user['email'],
            name=user.get('name'),
            picture=user.get('picture'),
            is_active=True
        )
    
    async def get_current_active_user(
        self,
        current_user: UserSession = Depends(get_current_user)
    ) -> UserSession:
        """
        Get current active user
        
        Args:
            current_user: Current user session
            
        Returns:
            Current active user session
            
        Raises:
            HTTPException: If user is not active
        """
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        return current_user
    
    def refresh_token(self, token: str) -> Optional[str]:
        """
        Refresh an existing token if it's close to expiration
        
        Args:
            token: Current JWT token
            
        Returns:
            New token if refreshed, None otherwise
        """
        token_data = self.decode_token(token)
        if not token_data:
            return None
        
        # Check if token expires within 1 hour
        exp_time = datetime.fromtimestamp(token_data.exp) if token_data.exp else None
        if exp_time and (exp_time - datetime.utcnow()).total_seconds() < 3600:
            # Refresh the token
            user_data = {
                'id': token_data.sub,
                'email': token_data.email,
                'name': token_data.name
            }
            return self.create_access_token(user_data)
        
        return None

# Global auth handler instance
auth_handler = AuthHandler()

# Dependency functions for FastAPI
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserSession:
    """FastAPI dependency to get current user"""
    return await auth_handler.get_current_user(credentials)

async def get_current_active_user(
    current_user: UserSession = Depends(get_current_user)
) -> UserSession:
    """FastAPI dependency to get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user