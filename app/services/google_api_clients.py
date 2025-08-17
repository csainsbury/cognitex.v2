"""
Google API service clients for authenticated API access
"""
import logging
from typing import Optional, Any, Dict
import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

class GoogleAPIClient:
    """
    Manages Google API service objects with OAuth2 authentication.
    Handles token storage, refresh, and service creation.
    """
    
    # Token storage directory
    TOKEN_DIR = Path("tokens")
    
    def __init__(self):
        """Initialize the Google API client manager"""
        # Ensure token directory exists
        self.TOKEN_DIR.mkdir(exist_ok=True)
        
        # Service cache
        self._services: Dict[str, Any] = {}
    
    def get_user_credentials(self, user_id: str, access_token: Optional[str] = None) -> Optional[Credentials]:
        """
        Get or create credentials for a user.
        
        Args:
            user_id: User identifier
            access_token: Optional access token from OAuth flow
            
        Returns:
            Google Credentials object or None if not available
        """
        token_file = self.TOKEN_DIR / f"{user_id}_token.pkl"
        creds = None
        
        # Try to load existing token
        if token_file.exists():
            try:
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)
                logger.debug(f"Loaded existing credentials for user {user_id}")
            except Exception as e:
                logger.error(f"Error loading token for user {user_id}: {e}")
        
        # Create credentials from access token if provided
        if not creds and access_token:
            # Sort scopes to ensure consistency
            sorted_scopes = sorted(['openid',
                                   'https://www.googleapis.com/auth/userinfo.email',
                                   'https://www.googleapis.com/auth/userinfo.profile',
                                   'https://www.googleapis.com/auth/gmail.readonly',
                                   'https://www.googleapis.com/auth/calendar.readonly'])
            
            creds = Credentials(
                token=access_token,
                refresh_token=None,  # Would need refresh token from OAuth
                token_uri='https://oauth2.googleapis.com/token',
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=sorted_scopes
            )
            # Save the credentials
            self.save_user_credentials(user_id, creds)
        
        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self.save_user_credentials(user_id, creds)
                logger.info(f"Refreshed credentials for user {user_id}")
            except Exception as e:
                logger.error(f"Error refreshing token for user {user_id}: {e}")
                return None
        
        return creds
    
    def save_user_credentials(self, user_id: str, creds: Credentials) -> None:
        """
        Save user credentials to disk.
        
        Args:
            user_id: User identifier
            creds: Credentials to save
        """
        token_file = self.TOKEN_DIR / f"{user_id}_token.pkl"
        try:
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
            logger.debug(f"Saved credentials for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving token for user {user_id}: {e}")
    
    def get_gmail_service(self, user_id: str, access_token: Optional[str] = None):
        """
        Get Gmail API service for a user.
        
        Args:
            user_id: User identifier
            access_token: Optional access token
            
        Returns:
            Gmail service object or None if authentication fails
        """
        service_key = f"{user_id}_gmail"
        
        # Check cache
        if service_key in self._services:
            return self._services[service_key]
        
        # Get credentials
        creds = self.get_user_credentials(user_id, access_token)
        if not creds:
            logger.error(f"No valid credentials for user {user_id}")
            return None
        
        try:
            # Build service
            service = build('gmail', 'v1', credentials=creds)
            self._services[service_key] = service
            logger.info(f"Created Gmail service for user {user_id}")
            return service
        except Exception as e:
            logger.error(f"Error creating Gmail service for user {user_id}: {e}")
            return None
    
    def get_calendar_service(self, user_id: str, access_token: Optional[str] = None):
        """
        Get Google Calendar API service for a user.
        
        Args:
            user_id: User identifier
            access_token: Optional access token
            
        Returns:
            Calendar service object or None if authentication fails
        """
        service_key = f"{user_id}_calendar"
        
        # Check cache
        if service_key in self._services:
            return self._services[service_key]
        
        # Get credentials
        creds = self.get_user_credentials(user_id, access_token)
        if not creds:
            logger.error(f"No valid credentials for user {user_id}")
            return None
        
        try:
            # Build service
            service = build('calendar', 'v3', credentials=creds)
            self._services[service_key] = service
            logger.info(f"Created Calendar service for user {user_id}")
            return service
        except Exception as e:
            logger.error(f"Error creating Calendar service for user {user_id}: {e}")
            return None
    
    def get_drive_service(self, user_id: str, access_token: Optional[str] = None):
        """
        Get Google Drive API service for a user.
        
        Args:
            user_id: User identifier
            access_token: Optional access token
            
        Returns:
            Drive service object or None if authentication fails
        """
        service_key = f"{user_id}_drive"
        
        # Check cache
        if service_key in self._services:
            return self._services[service_key]
        
        # Get credentials
        creds = self.get_user_credentials(user_id, access_token)
        if not creds:
            logger.error(f"No valid credentials for user {user_id}")
            return None
        
        try:
            # Build service
            service = build('drive', 'v3', credentials=creds)
            self._services[service_key] = service
            logger.info(f"Created Drive service for user {user_id}")
            return service
        except Exception as e:
            logger.error(f"Error creating Drive service for user {user_id}: {e}")
            return None
    
    def clear_user_tokens(self, user_id: str) -> None:
        """
        Clear stored tokens for a user.
        
        Args:
            user_id: User identifier
        """
        token_file = self.TOKEN_DIR / f"{user_id}_token.pkl"
        if token_file.exists():
            token_file.unlink()
            logger.info(f"Cleared tokens for user {user_id}")
        
        # Clear cached services
        keys_to_remove = [k for k in self._services.keys() if k.startswith(user_id)]
        for key in keys_to_remove:
            del self._services[key]

# Global instance
google_api_client = GoogleAPIClient()