#!/bin/bash
# SENTIMENTSWIPE V2 - Quick Start

echo "🤖 SentimentSwipe V2 Trading Agent"
echo "=================================="

# Detect Python
PYTHON=""
for py in python python3 python3.12; do
    if command -v $py &>/dev/null; then
        PYTHON=$py
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python not found"
    echo "Install from: https://www.python.org/downloads/"
    exit 1
fi

cd "$(dirname "$0")/sentimentswipe"

# Check dependencies
echo "Checking dependencies..."
$PYTHON -c "import web3, schedule, flask, dotenv, requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    $PYTHON -m pip install -r requirements.txt
fi

case "$1" in
    paper)
        echo "Starting PAPER TRADING mode..."
        $PYTHON agent.py --paper --capital ${2:-100}
        ;;
    live)
        echo "Starting LIVE TRADING mode..."
        if [ -z "$3" ]; then
            echo "Usage: ./run.sh live <PRIVATE_KEY> <CAPITAL>"
            exit 1
        fi
        $PYTHON agent.py --key $2 --capital ${3:-100}
        ;;
    register)
        echo "Registering for competition..."
        if [ -z "$2" ]; then
            echo "Usage: ./run.sh register <PRIVATE_KEY>"
            exit 1
        fi
        $PYTHON agent.py --key $2 --register
        ;;
    status)
        echo "Agent status:"
        $PYTHON agent.py --status
        ;;
    dashboard)
        echo "Starting dashboard on port 5000..."
        cd dashboard && $PYTHON app.py
        ;;
    test)
        echo "Running one test cycle..."
        $PYTHON agent.py --paper --once
        ;;
    *)
        echo "Usage: ./run.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  paper [capital]     - Paper trade (default \$100)"
        echo "  live <key> [cap]    - Live trading (requires private key)"
        echo "  register <key>      - Register agent for competition"
        echo "  status              - Show agent status"
        echo "  dashboard           - Start monitoring dashboard"
        echo "  test                - Run one test cycle"
        echo ""
        echo "Examples:"
        echo "  ./run.sh paper              # Paper trade with \$100"
        echo "  ./run.sh paper 200          # Paper trade with \$200"
        echo "  ./run.sh live <KEY> 100     # Live trade with \$100"
        echo "  ./run.sh test               # Test one cycle"
        ;;
esac