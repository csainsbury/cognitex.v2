#!/usr/bin/env python3
"""
Test Firebase connection and configuration
"""
import sys
import os
import json

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Firebase Connection Test")
print("=" * 50)

# Check if credentials file exists
creds_file = "firebase-credentials.json"
if os.path.exists(creds_file):
    print(f"✅ Found {creds_file}")
    try:
        with open(creds_file, 'r') as f:
            creds = json.load(f)
            print(f"  Project ID: {creds.get('project_id', 'Not found')}")
    except Exception as e:
        print(f"  ⚠️ Error reading credentials: {e}")
else:
    print(f"❌ {creds_file} not found!")

print("\nTesting Firebase initialization...")

try:
    from app.database.firebase_client import firebase_client
    from app.config import settings
    
    print(f"  Firebase credentials path: {settings.FIREBASE_CREDENTIALS_PATH}")
    
    # Try to initialize Firebase
    firebase_client.initialize()
    print("✅ Firebase initialized successfully!")
    
    # Test creating a test user
    test_user = {
        'id': 'test_user_123',
        'email': 'test@example.com',
        'name': 'Test User',
        'provider': 'test'
    }
    
    print("\nTesting Firestore operations...")
    user = firebase_client.get_or_create_user(test_user)
    print(f"✅ Successfully created/retrieved test user: {user.get('email')}")
    
    # Clean up test user
    firebase_client.delete_user('test_user_123')
    print("✅ Test user cleaned up")
    
    print("\n" + "=" * 50)
    print("✅ Firebase is working correctly!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("  Make sure all dependencies are installed")
    
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}")
    print("\nPossible issues:")
    print("1. Invalid credentials file")
    print("2. Missing Firebase project")
    print("3. Firestore not enabled in Firebase Console")
    print("4. Network/firewall issues")

print("\n" + "=" * 50)
print("Next: Test Google Sign-In at http://cognitex.org:8000")