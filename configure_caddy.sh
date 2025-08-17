#!/bin/bash
# Script to configure Caddy for Cognitex

echo "Configuring Caddy for Cognitex"
echo "=============================="

# Copy Caddyfile to Caddy directory
echo "Installing Caddyfile..."
sudo cp Caddyfile /etc/caddy/Caddyfile

# Create log directory
echo "Creating log directory..."
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy

# Test configuration
echo "Testing Caddy configuration..."
sudo caddy validate --config /etc/caddy/Caddyfile

if [ $? -eq 0 ]; then
    echo "✅ Configuration is valid!"
else
    echo "❌ Configuration error. Please check the Caddyfile."
    exit 1
fi

# Reload Caddy with new configuration
echo "Reloading Caddy..."
sudo systemctl reload caddy

# Enable Caddy to start on boot
echo "Enabling Caddy on boot..."
sudo systemctl enable caddy

# Start Caddy if not running
echo "Starting Caddy..."
sudo systemctl start caddy

# Check status
echo ""
echo "Caddy Status:"
sudo systemctl status caddy --no-pager

echo ""
echo "✅ Caddy configuration complete!"
echo ""
echo "Your site should now be accessible at:"
echo "  https://cognitex.org"
echo ""
echo "Note: It may take a minute for SSL certificates to be obtained."
echo "Check logs: sudo journalctl -u caddy -f"