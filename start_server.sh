#!/bin/bash
# Starts the media-stream server and the ngrok tunnel together.
# Run this first, then use place_call.sh (or test_media_stream_call.py
# directly) in another terminal to actually place a call.

set -e

echo "Starting media-stream server on port 8000..."
python3 -u ws_echo_test.py > /tmp/ws_echo_server.log 2>&1 &
SERVER_PID=$!
sleep 2

echo "Starting ngrok tunnel..."
ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
sleep 4

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])")
NGROK_HOST=${NGROK_URL#https://}

echo ""
echo "Server running (PID $SERVER_PID), tunnel running (PID $NGROK_PID)."
echo "Public host: $NGROK_HOST"
echo ""
echo "To place a call, in another terminal run:"
echo "  python3 test_media_stream_call.py $NGROK_HOST <scenario_name>"
echo ""
echo "Example scenario names are in scenarios/ (e.g. 01_baseline)."
echo "Server logs: tail -f /tmp/ws_echo_server.log"
echo ""
echo "Press Ctrl+C to stop both processes."

trap "kill $SERVER_PID $NGROK_PID 2>/dev/null" EXIT
wait
