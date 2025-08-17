"""
Authentication API routes
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.auth import (
    auth_handler, get_current_active_user,
    GoogleAuthRequest, AuthResponse, UserSession,
    User, UserPreferences
)
from app.database.firebase_client import firebase_client

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"],
    responses={404: {"description": "Not found"}},
)

@router.post("/google", response_model=AuthResponse)
async def google_login(auth_request: GoogleAuthRequest):
    """
    Authenticate user with Google OAuth
    
    Args:
        auth_request: Google authentication request with ID token
        
    Returns:
        Authentication response with user and token
    """
    try:
        result = await auth_handler.authenticate_google_user(auth_request)
        return AuthResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )

@router.get("/me", response_model=User)
async def get_current_user_profile(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Get current user's profile
    
    Args:
        current_user: Current authenticated user session
        
    Returns:
        User profile data
    """
    user_data = firebase_client.get_user(current_user.user_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return User(**user_data)

@router.post("/logout")
async def logout(current_user: UserSession = Depends(get_current_active_user)):
    """
    Logout current user (client should delete token)
    
    Args:
        current_user: Current authenticated user session
        
    Returns:
        Success message
    """
    # In a stateless JWT system, logout is handled client-side
    # Here we just acknowledge the logout request
    logger.info(f"User {current_user.email} logged out")
    
    return {"message": "Logged out successfully"}

@router.post("/refresh")
async def refresh_token(current_user: UserSession = Depends(get_current_active_user)):
    """
    Refresh authentication token
    
    Args:
        current_user: Current authenticated user session
        
    Returns:
        New authentication token
    """
    user_data = firebase_client.get_user(current_user.user_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create new token
    new_token = auth_handler.create_access_token(user_data)
    
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": auth_handler.expiration_minutes * 60
    }

@router.get("/preferences", response_model=UserPreferences)
async def get_user_preferences(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Get user preferences
    
    Args:
        current_user: Current authenticated user session
        
    Returns:
        User preferences
    """
    preferences = firebase_client.get_user_preferences(current_user.user_id)
    if not preferences:
        # Return default preferences
        return UserPreferences()
    
    return UserPreferences(**preferences)

@router.put("/preferences", response_model=UserPreferences)
async def update_user_preferences(
    preferences: UserPreferences,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Update user preferences
    
    Args:
        preferences: New user preferences
        current_user: Current authenticated user session
        
    Returns:
        Updated preferences
    """
    success = firebase_client.update_user_preferences(
        current_user.user_id,
        preferences.dict()
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )
    
    return preferences

@router.delete("/account")
async def delete_account(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Delete user account
    
    Args:
        current_user: Current authenticated user session
        
    Returns:
        Success message
    """
    success = firebase_client.delete_user(current_user.user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )
    
    logger.info(f"Deleted account for user {current_user.email}")
    return {"message": "Account deleted successfully"}

@router.get("/verify")
async def verify_token(current_user: UserSession = Depends(get_current_active_user)):
    """
    Verify if token is valid
    
    Args:
        current_user: Current authenticated user session
        
    Returns:
        Validation status
    """
    return {
        "valid": True,
        "user_id": current_user.user_id,
        "email": current_user.email
    }