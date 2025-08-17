#!/bin/bash
# Script to install Caddy web server

echo "Installing Caddy Web Server"
echo "==========================="

# Install required packages
echo "Installing dependencies..."
sudo apt update
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https

# Add Caddy GPG key
echo "Adding Caddy GPG key..."
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg

# Add Caddy repository
echo "Adding Caddy repository..."
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list

# Update and install Caddy
echo "Installing Caddy..."
sudo apt update
sudo apt install -y caddy

# Check installation
if command -v caddy &> /dev/null; then
    echo "✅ Caddy installed successfully!"
    caddy version
else
    echo "❌ Caddy installation failed"
    exit 1
fi

echo ""
echo "Next steps:"
echo "1. Run: ./configure_caddy.sh"
echo "2. Start Caddy: sudo systemctl start caddy"