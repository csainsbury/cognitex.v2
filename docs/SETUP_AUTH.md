# Authentication Setup Guide

This guide walks through setting up Google OAuth and Firebase for Cognitex.

## Prerequisites

1. Google Cloud Console account
2. Firebase project

## Google OAuth Setup

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing one

2. **Enable Required APIs** (for Cognitex features)
   - Navigate to "APIs & Services" > "Library"
   - For basic authentication: No additional APIs needed
   - For email access: Enable "Gmail API"
   - For calendar access: Enable "Google Calendar API"  
   - For Drive access: Enable "Google Drive API"
   
   Note: Basic OAuth authentication (getting user profile) doesn't require enabling any APIs - it's automatically available with OAuth 2.0 credentials.

3. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Configure consent screen if prompted:
     - App name: Cognitex
     - User support email: Your email
     - Authorized domains: Your domain (localhost for development)
   - Application type: Web application
   - Name: Cognitex Web Client
   - Authorized JavaScript origins:
     - http://localhost:8000 (for development)
     - Your production URL
   - Authorized redirect URIs:
     - http://localhost:8000/auth/callback
     - Your production callback URL

4. **Get Client ID and Secret**
   - Copy the Client ID and Client Secret
   - Add them to your `.env` file:
     ```
     GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
     GOOGLE_CLIENT_SECRET=your-client-secret
     ```

## Firebase Setup

1. **Create Firebase Project**
   - Go to [Firebase Console](https://console.firebase.google.com)
   - Create a new project or use existing one

2. **Enable Firestore**
   - Navigate to "Firestore Database"
   - Click "Create database"
   - Choose production or test mode
   - Select region closest to your users

3. **Generate Service Account Key**
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Save the JSON file as `firebase-credentials.json`
   - Place it in your project root (it's gitignored)
   - Update `.env`:
     ```
     FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
     ```

## Environment Configuration

Your complete `.env` file should include:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Firebase
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json

# JWT (generate a secure secret)
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key
```

## Testing Authentication

1. Start the application:
   ```bash
   uvicorn app.main:app --reload
   ```

2. Navigate to http://localhost:8000

3. Click "Sign in with Google"

4. After successful authentication, you should see your user info

## Security Notes

- **Never commit credentials**: Ensure `firebase-credentials.json` and `.env` are in `.gitignore`
- **Use HTTPS in production**: OAuth requires secure connections
- **Rotate secrets regularly**: Change JWT secrets periodically
- **Validate tokens**: Always verify tokens on the backend

## Troubleshooting

### "Invalid client" error
- Verify GOOGLE_CLIENT_ID is correct
- Check authorized origins include your current URL

### Firebase initialization fails
- Ensure firebase-credentials.json exists and is valid
- Check file path in FIREBASE_CREDENTIALS_PATH

### JWT errors
- Ensure SECRET_KEY and JWT_SECRET_KEY are set
- Check token expiration settings

## Production Considerations

1. **Use environment variables** instead of files for credentials
2. **Enable CORS** only for your production domain
3. **Set up** proper SSL certificates
4. **Configure** rate limiting on auth endpoints
5. **Monitor** authentication logs for suspicious activity