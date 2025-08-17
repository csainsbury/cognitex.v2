#!/bin/bash

# Script to push to GitHub with token authentication

echo "Push to GitHub Repository: csainsbury/cognitex.v2"
echo "================================================"
echo ""
echo "To push to GitHub, you need a Personal Access Token (PAT)."
echo ""
echo "Steps to get a token:"
echo "1. Go to: https://github.com/settings/tokens/new"
echo "2. Give it a name (e.g., 'cognitex-push')"
echo "3. Select 'repo' scope"
echo "4. Generate token and copy it"
echo ""
read -p "Enter your GitHub Personal Access Token: " TOKEN
echo ""

if [ -z "$TOKEN" ]; then
    echo "Error: No token provided"
    exit 1
fi

echo "Pushing to GitHub..."
git push https://$TOKEN@github.com/csainsbury/cognitex.v2.git main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pushed to GitHub!"
    echo "View your repository at: https://github.com/csainsbury/cognitex.v2"
    
    # Set up the remote to use token for future pushes (optional)
    read -p "Save this token for future pushes? (y/n): " SAVE
    if [ "$SAVE" = "y" ]; then
        git remote set-url origin https://$TOKEN@github.com/csainsbury/cognitex.v2.git
        echo "Token saved in git remote URL (stored in .git/config)"
        echo "Future pushes can use: git push"
    fi
else
    echo ""
    echo "❌ Push failed. Please check:"
    echo "1. The repository exists at https://github.com/csainsbury/cognitex.v2"
    echo "2. Your token has the correct permissions"
    echo "3. You have access to the repository"
fi