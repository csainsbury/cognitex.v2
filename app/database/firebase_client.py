"""
Firebase client for Firestore database interactions
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore, auth
from google.cloud.firestore import Client
from google.api_core import exceptions

from app.config import settings

logger = logging.getLogger(__name__)

class FirebaseClient:
    """
    Singleton Firebase client for all Firestore operations
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.db: Optional[Client] = None
            self.app = None
            self._initialized = True
    
    def initialize(self) -> None:
        """
        Initialize Firebase Admin SDK with service account credentials
        """
        if self.db is not None:
            logger.info("Firebase already initialized")
            return
        
        try:
            if settings.FIREBASE_CREDENTIALS_PATH:
                # Use service account credentials
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                self.app = firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized with service account")
            else:
                # Try default credentials (for cloud environments)
                self.app = firebase_admin.initialize_app()
                logger.info("Firebase initialized with default credentials")
            
            self.db = firestore.client()
            logger.info("Firestore client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user document from Firestore
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            User document data or None if not found
        """
        if not self.db:
            logger.error("Firebase not initialized")
            return None
        
        try:
            doc_ref = self.db.collection('users').document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                logger.info(f"User {user_id} not found")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    def get_or_create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get existing user or create new user in Firestore
        
        Args:
            user_data: Dictionary containing user information
            
        Returns:
            User document data
        """
        if not self.db:
            logger.error("Firebase not initialized")
            raise RuntimeError("Firebase not initialized")
        
        user_id = user_data.get('id') or user_data.get('uid')
        if not user_id:
            raise ValueError("User ID is required")
        
        try:
            # Try to get existing user
            existing_user = self.get_user(user_id)
            if existing_user:
                logger.info(f"Found existing user: {user_id}")
                # Update last login
                self.update_user(user_id, {"last_login": datetime.utcnow()})
                return existing_user
            
            # Create new user
            user_doc = {
                'id': user_id,
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'picture': user_data.get('picture'),
                'provider': user_data.get('provider', 'google'),
                'created_at': datetime.utcnow(),
                'last_login': datetime.utcnow(),
                'preferences': {
                    'synthesis_enabled': True,
                    'notification_enabled': True,
                    'timezone': 'UTC'
                },
                'metadata': user_data.get('metadata', {})
            }
            
            # Remove None values
            user_doc = {k: v for k, v in user_doc.items() if v is not None}
            
            # Create document in Firestore
            doc_ref = self.db.collection('users').document(user_id)
            doc_ref.set(user_doc)
            
            logger.info(f"Created new user: {user_id}")
            return user_doc
            
        except Exception as e:
            logger.error(f"Error creating/getting user {user_id}: {e}")
            raise
    
    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update user document in Firestore
        
        Args:
            user_id: The user's unique identifier
            update_data: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db:
            logger.error("Firebase not initialized")
            return False
        
        try:
            doc_ref = self.db.collection('users').document(user_id)
            
            # Add updated_at timestamp
            update_data['updated_at'] = datetime.utcnow()
            
            doc_ref.update(update_data)
            logger.info(f"Updated user {user_id}")
            return True
            
        except exceptions.NotFound:
            logger.error(f"User {user_id} not found for update")
            return False
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return False
    
    def verify_id_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a Firebase ID token
        
        Args:
            id_token: The Firebase ID token to verify
            
        Returns:
            Decoded token claims or None if invalid
        """
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            logger.error(f"Error verifying ID token: {e}")
            return None
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete user document from Firestore
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db:
            logger.error("Firebase not initialized")
            return False
        
        try:
            doc_ref = self.db.collection('users').document(user_id)
            doc_ref.delete()
            logger.info(f"Deleted user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user preferences
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            User preferences or None if not found
        """
        user = self.get_user(user_id)
        if user:
            return user.get('preferences', {})
        return None
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Update user preferences
        
        Args:
            user_id: The user's unique identifier
            preferences: Dictionary of preferences to update
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_user(user_id, {'preferences': preferences})

# Global instance
firebase_client = FirebaseClient()