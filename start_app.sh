#!/bin/bash

# Activate virtual environment
source transcription/bin/activate

# Start ngrok in the background
python start_ngrok.py &
NGROK_PID=$!

# Wait a moment for ngrok to start
sleep 2

# Start Flask application
flask run

# When Flask is stopped, also stop ngrok
kill $NGROK_PID 