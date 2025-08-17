#!/usr/bin/env python3
"""
Test configuration and show what needs to be installed
"""
import sys
import os

print("Cognitex Configuration Test")
print("=" * 50)

# Check Python version
print(f"Python version: {sys.version}")

# Check if we can load the config
try:
    # Add app to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Try to import our config
    from app.config.settings import settings
    
    print("\n✅ Configuration loaded successfully!")
    print(f"  App Name: {settings.APP_NAME}")
    print(f"  Environment: {settings.APP_ENV}")
    print(f"  Google Client ID: {settings.GOOGLE_CLIENT_ID[:20]}...")
    print(f"  Redirect URI: {settings.GOOGLE_REDIRECT_URI}")
    
except ImportError as e:
    print(f"\n❌ Missing dependency: {e}")
    print("\nYou need to install dependencies first:")
    print("1. Install pip: curl https://bootstrap.pypa.io/get-pip.py | python3")
    print("2. Install dependencies: python3 -m pip install --user -r requirements.txt")

print("\n" + "=" * 50)
print("To run the application:")
print("1. Ensure you have pip and venv installed")
print("2. Create virtual environment: python3 -m venv venv")
print("3. Activate it: source venv/bin/activate")
print("4. Install dependencies: pip install -r requirements.txt")
print("5. Run: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
print("\nOr use Python directly: python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000")