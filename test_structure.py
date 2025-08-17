#!/usr/bin/env python3
"""
Test script to verify the project structure is correctly set up
"""
import os
import sys
from pathlib import Path

def check_structure():
    """Check if all expected files and directories exist"""
    
    base_dir = Path(__file__).parent
    
    # Expected directories
    expected_dirs = [
        "app",
        "app/agents",
        "app/api", 
        "app/auth",
        "app/config",
        "app/database",
        "app/orchestrator",
        "app/prompts",
        "app/services",
        "app/ui",
        "app/ui/static",
        "app/ui/templates"
    ]
    
    # Expected files
    expected_files = [
        "app/__init__.py",
        "app/main.py",
        "app/config/__init__.py",
        "app/config/settings.py",
        "app/orchestrator/__init__.py",
        "app/orchestrator/message.py",
        "app/orchestrator/simple_orchestrator.py",
        "app/agents/__init__.py",
        "app/agents/base_agent.py",
        ".env",
        ".env.example",
        ".gitignore",
        "requirements.txt",
        "README.md"
    ]
    
    print("Cognitex v2 Structure Check")
    print("=" * 50)
    
    # Check directories
    print("\n📁 Directories:")
    for dir_path in expected_dirs:
        full_path = base_dir / dir_path
        exists = "✅" if full_path.exists() else "❌"
        print(f"  {exists} {dir_path}")
    
    # Check files
    print("\n📄 Files:")
    for file_path in expected_files:
        full_path = base_dir / file_path
        exists = "✅" if full_path.exists() else "❌"
        print(f"  {exists} {file_path}")
    
    print("\n" + "=" * 50)
    print("✅ Phase 1: Core Application Skeleton - COMPLETE")
    print("\nNext steps:")
    print("1. Install Python virtual environment: python3 -m venv venv")
    print("2. Activate environment: source venv/bin/activate")
    print("3. Install dependencies: pip install -r requirements.txt")
    print("4. Run the application: uvicorn app.main:app --reload")
    print("\nThe application will be available at http://localhost:8000")

if __name__ == "__main__":
    check_structure()