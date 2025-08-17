"""
OAuth routes for Google API access (Gmail, Calendar, etc.)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os

from app.config import settings
from app.auth import get_current_active_user, UserSession
from app.services.google_api_clients import google_api_client

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/oauth",
    tags=["oauth"],
    responses={404: {"description": "Not found"}},
)

# OAuth scopes we need - use full URLs to match what Google returns
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def get_oauth_flow(state=None):
    """Create OAuth flow instance"""
    # Sort scopes to ensure consistency
    sorted_scopes = sorted(SCOPES)
    
    # Create flow from client config
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        },
        scopes=sorted_scopes,
        state=state
    )
    
    # Set redirect URI
    flow.redirect_uri = "https://cognitex.org/api/oauth/callback"
    
    return flow

@router.get("/authorize")
async def authorize_google(
    request: Request,
    user_id: str
):
    """
    Start OAuth flow to get Gmail/Calendar access
    """
    try:
        # Create flow
        flow = get_oauth_flow()
        
        # Get authorization URL with user_id as additional parameter
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Get refresh token
            prompt='consent',  # Force consent screen to get refresh token
            state=user_id  # Pass user_id as state
        )
        
        logger.info(f"Starting OAuth flow for user {user_id}")
        
        # Redirect to Google
        return RedirectResponse(url=authorization_url)
        
    except Exception as e:
        logger.error(f"OAuth authorization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str,
    state: str
):
    """
    Handle OAuth callback from Google
    """
    try:
        # User ID is passed as state
        user_id = state
        
        # Create flow with state
        flow = get_oauth_flow(state=state)
        
        # Exchange code for tokens
        flow.fetch_token(code=code)
        
        # Get credentials
        credentials = flow.credentials
        
        # Save credentials for user
        google_api_client.save_user_credentials(user_id, credentials)
        
        logger.info(f"OAuth successful for user {user_id}")
        
        # Return success page
        return HTMLResponse(content="""
            <html>
            <head>
                <title>Authorization Successful</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    }
                    .container {
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                        text-align: center;
                        max-width: 400px;
                    }
                    h1 { color: #333; }
                    p { color: #666; margin: 20px 0; }
                    .btn {
                        background: #667eea;
                        color: white;
                        padding: 12px 30px;
                        border: none;
                        border-radius: 5px;
                        text-decoration: none;
                        display: inline-block;
                        margin-top: 20px;
                        cursor: pointer;
                    }
                    .btn:hover { background: #5a67d8; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✅ Authorization Successful!</h1>
                    <p>You've successfully granted access to your Gmail and Calendar.</p>
                    <p>You can now use all email and calendar features in Cognitex.</p>
                    <a href="/dashboard" class="btn">Go to Dashboard</a>
                </div>
            </body>
            </html>
        """)
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        
        # Return error page
        return HTMLResponse(content=f"""
            <html>
            <head>
                <title>Authorization Failed</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: #f5f5f5;
                    }}
                    .container {{
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        text-align: center;
                        max-width: 400px;
                    }}
                    h1 {{ color: #e53e3e; }}
                    p {{ color: #666; margin: 20px 0; }}
                    .error {{ 
                        background: #fed7d7; 
                        color: #c53030; 
                        padding: 10px; 
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                    .btn {{
                        background: #667eea;
                        color: white;
                        padding: 12px 30px;
                        border: none;
                        border-radius: 5px;
                        text-decoration: none;
                        display: inline-block;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>❌ Authorization Failed</h1>
                    <p>There was an error authorizing access to your Google account.</p>
                    <div class="error">Error: {str(e)}</div>
                    <a href="/dashboard" class="btn">Back to Dashboard</a>
                </div>
            </body>
            </html>
        """, status_code=400)

@router.get("/status")
async def oauth_status(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Check if user has valid OAuth tokens
    """
    # Check if we have credentials
    creds = google_api_client.get_user_credentials(current_user.user_id)
    
    return {
        "has_credentials": creds is not None,
        "is_valid": creds is not None and not (creds.expired if hasattr(creds, 'expired') else False),
        "scopes": SCOPES
    }

@router.post("/revoke")
async def revoke_access(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Revoke OAuth access for the current user
    """
    google_api_client.clear_user_tokens(current_user.user_id)
    
    return {"message": "Access revoked successfully"}