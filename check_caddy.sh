#!/bin/bash
# Check Caddy status and troubleshoot

echo "Checking Caddy Status"
echo "===================="

# Check if Caddy is running
if systemctl is-active --quiet caddy; then
    echo "✅ Caddy is running"
else
    echo "❌ Caddy is not running"
    echo "Start with: sudo systemctl start caddy"
fi

# Check ports
echo ""
echo "Port Status:"
ss -tln | grep -E ':80|:443'

# Check recent logs
echo ""
echo "Recent Caddy Logs:"
sudo journalctl -u caddy -n 20 --no-pager

# Check certificates
echo ""
echo "Certificate Status:"
sudo caddy list-certificates

echo ""
echo "Troubleshooting Tips:"
echo "1. Check full logs: sudo journalctl -u caddy -f"
echo "2. Test HTTP access: curl -v http://cognitex.org"
echo "3. Test HTTPS access: curl -v https://cognitex.org"
echo "4. Restart Caddy: sudo systemctl restart caddy"