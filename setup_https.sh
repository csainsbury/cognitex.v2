#!/bin/bash
# Complete HTTPS setup script for Cognitex

echo "Cognitex HTTPS Setup"
echo "===================="
echo ""
echo "This script will:"
echo "1. Install Caddy web server"
echo "2. Configure SSL with Let's Encrypt"
echo "3. Set up reverse proxy to FastAPI"
echo ""
echo "Requirements:"
echo "- sudo access"
echo "- Port 80 and 443 available"
echo "- cognitex.org DNS pointing to this server"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 1
fi

# Step 1: Install Caddy
echo ""
echo "Step 1: Installing Caddy..."
./install_caddy.sh

if [ $? -ne 0 ]; then
    echo "Caddy installation failed"
    exit 1
fi

# Step 2: Configure Caddy
echo ""
echo "Step 2: Configuring Caddy..."
./configure_caddy.sh

if [ $? -ne 0 ]; then
    echo "Caddy configuration failed"
    exit 1
fi

# Step 3: Ensure FastAPI is running
echo ""
echo "Step 3: Checking FastAPI..."
if pgrep -f "uvicorn" > /dev/null; then
    echo "✅ FastAPI is running"
else
    echo "⚠️  FastAPI is not running. Starting it..."
    ./run.sh &
    sleep 5
fi

echo ""
echo "===================="
echo "✅ HTTPS Setup Complete!"
echo ""
echo "Your application should now be accessible at:"
echo "  https://cognitex.org"
echo ""
echo "Google OAuth should now work with HTTPS!"
echo ""
echo "To check Caddy logs:"
echo "  sudo journalctl -u caddy -f"
echo ""
echo "To check SSL certificate status:"
echo "  sudo caddy list-certificates"