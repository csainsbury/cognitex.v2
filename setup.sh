#!/bin/bash
# Cognitex Setup Script

echo "Cognitex Setup"
echo "=============="

# Check if pip is installed
if ! python3 -m pip --version &> /dev/null; then
    echo "Installing pip..."
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py --user
    rm get-pip.py
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "✓ pip is already installed"
fi

# Check if venv module is available
if python3 -m venv --help &> /dev/null; then
    echo "✓ venv module is available"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    else
        echo "✓ Virtual environment already exists"
    fi
    
    # Activate virtual environment
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    # Install dependencies
    echo "Installing dependencies..."
    pip install -r requirements.txt
    
    echo ""
    echo "✅ Setup complete!"
    echo ""
    echo "To run the application:"
    echo "  source venv/bin/activate"
    echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    echo ""
    echo "Or run directly:"
    echo "  ./run.sh"
else
    echo "⚠️  venv module not available"
    echo "Installing dependencies globally (user)..."
    python3 -m pip install --user -r requirements.txt
    
    echo ""
    echo "✅ Setup complete!"
    echo ""
    echo "To run the application:"
    echo "  python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
fi