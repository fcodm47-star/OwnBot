#!/bin/bash

echo "==================================="
echo "CODM Bot Setup for Replit"
echo "==================================="

# Create directories
echo "📁 Creating directories..."
mkdir -p combo combo/hits combo/clean combo/processed
mkdir -p proxy proxy/working proxy/bad proxy/all
mkdir -p data

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Create sample files
echo "📝 Creating sample files..."

# Sample proxy file
cat > proxy/proxy.txt << 'EOF'
# Add your proxies here - one per line
# Format: host:port or host:port:username:password
# Example:
# 192.168.1.1:8080
# proxy.example.com:3128:user:pass
EOF

# Sample combo file
cat > combo/sample.txt << 'EOF'
# Sample combo file
# Format: username:password
# testuser1:password123
# testuser2:pass456
EOF

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit manager_bot.py and add your MANAGER_BOT_TOKEN"
echo "2. Run: python3 manager_bot.py"
echo "3. Message your manager bot on Telegram with /start"
echo ""