# This is a simple web app to process transcriptions using the Gladia API.
# To start:
# Make sure you've installed all the dependencies
# Run `python start_ngrok.py` to start a local server (to catch the response from Gladia)
# Run `flask --app flask_app --debug run`
# Run `python -m flask run`
# Visit the `localhost` page
# Upload a file through the page, and keep the app running at least until Gladia returns a transcript.

import os
import sys
import threading
import json


# Imports for ngrok integration
from pyngrok import ngrok
import requests
from dotenv import load_dotenv
from pydub import AudioSegment
from alive_progress import alive_bar
from flask import Flask, request, jsonify, render_template
from email_utils import send_confirmation_email, send_completion_email
from transcription_utils import parse_response, transcribe_audio_file_requests


print(f"Running in directory: {os.getcwd()}")


load_dotenv()
gladia_api_key = os.getenv("GLADIA_API_KEY_2")
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
ngrok_authtoken = os.getenv("NGROK_AUTHTOKEN")
mailgun_api_key = os.getenv("MAILGUN_API_KEY")
mailgun_domain = os.getenv("MAILGUN_DOMAIN")

# Add this line to check if the API key is loaded
print(f"Gladia API Key loaded: {'Yes' if gladia_api_key else 'No'}")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "temp_uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def get_ngrok_url():
    """
    Retrieves the ngrok URL from a local file.
    
    Returns:
        str or None: The ngrok URL if found in ngrok_url.txt, None if file not found
    """
    try:
        with open("ngrok_url.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print("ngrok URL file not found. Make sure to run start_ngrok.py first.")
        return None


# Determine if we're in development mode
is_development = os.getenv("DEBUG", "False").lower() == "true"

# Set up ngrok if in development mode
if is_development:
    print("Development mode detected. Setting up ngrok tunnel.")
    ngrok_url = get_ngrok_url()
    if ngrok_url:
        print(f"Ngrok tunnel established: {ngrok_url}")
    else:
        print("Failed to establish ngrok tunnel. Exiting.")
        sys.exit(1)
else:
    print("Ngrok not needed in production mode.")


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/transcribe", methods=["POST"])
@app.route("/transcribe", methods=["POST"])
def transcribe():
    vocab = request.form.get("vocab", "")
    email = request.form.get("email")
    file = request.files.get("file")

    if not file:
        return render_template("response.html", message="No file uploaded.")

    # Process the vocabulary input
    custom_vocab = [word.strip() for word in vocab.split(",") if word.strip()]

    # Save the uploaded file temporarily
    temp_file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(temp_file_path)

    callback_url = (
        ngrok_url + "/webhook"
        if is_development
        else "https://podcast-transcriber.onrender.com/webhook"
    )
    print(f"Callback URL: {callback_url}")

    try:
        with open(temp_file_path, "rb") as audio_file:
            # response = transcribe_deepgram_audio(audio_file, callback_url, deepgram_api_key, custom_vocab)
            response = transcribe_audio_file_requests(
                audio_file, callback_url, deepgram_api_key, custom_vocab
            )
        print(
            f"API response: {str(response)[:100]}..."
        )  # Print only first 100 characters
    finally:
        # Clean up the temporary file
        os.remove(temp_file_path)

    recipient_email = email or os.getenv("TEST_EMAIL")

    # Send a confirmation email to the user
    if recipient_email:
        try:
            email_response = send_confirmation_email(recipient_email)
            if email_response.status_code == 200:
                email_message = "Confirmation email sent."
            else:
                email_message = f"Failed to send confirmation email. Status code: {email_response.status_code}"
        except requests.Timeout:
            email_message = "Failed to send confirmation email due to timeout."
        except requests.RequestException as e:
            email_message = f"Failed to send confirmation email. Error: {str(e)}"
    else:
        email_message = "No email provided."
    print(f"Email message: {email_message}")

    # Return a response to the user
    return render_template(
        "response.html",
        message=f"Transcription in progress. Check {recipient_email} for results.",
    )


def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension.

    Args:
        filename (str): Name of the file to check

    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    allowed_extensions = {"mp3", "wav"}  # adjust as needed
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def process_transcript(data):
    """
    Process the transcript data received from Deepgram API.
    
    Args:
        data (dict): JSON data containing the transcript and metadata from Deepgram
        
    Returns:
        None: Writes transcript to file and sends email notification
    """
    try:
        response_to_md = parse_response(data)
        transcript_id = data["metadata"]["request_id"]
        print(f"Transcription ID: {transcript_id}. Now writing to file.")
        os.makedirs("transcriptions", exist_ok=True)
        transcript_path = f"transcriptions/transcript-{transcript_id}.md"
        with open(transcript_path, "w") as f:
            f.write(response_to_md)

        recipient_email = os.getenv("TEST_EMAIL")
        if recipient_email:
            try:
                email_response = send_completion_email(recipient_email, transcript_path)
                email_message = (
                    "Completion email sent."
                    if email_response.status_code == 200
                    else f"Failed to send completion email. Status code: {email_response.status_code}"
                )
            except requests.RequestException as e:
                email_message = f"Failed to send completion email. Error: {str(e)}"
        else:
            email_message = "No email provided."
        print(email_message)
    except Exception as e:
        print(f"Error processing transcript: {str(e)}")


@app.route("/webhook", methods=["GET", "OPTIONS", "POST"])
def webhook():
    print("Webhook hit with method:", request.method)
    print("Request headers:", dict(request.headers))
    # print("Request body:", request.get_data(as_text=True))

    # Allow GET requests during development for testing
    if request.method == "GET":
        return jsonify({"status": "webhook endpoint is accessible"}), 200
    if request.method == "OPTIONS":
        # Pre-flight request. Reply successfully:
        response = app.make_default_options_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, x-gladia-key"
        return response

    elif request.method == "POST":
        try:

            data = request.json
            print("Received JSON data from Deepgram API.")

            # Immediately return a success response
            response = jsonify(
                {
                    "status": "success",
                    "message": "Webhook received and processing started",
                }
            )

            # Start processing in a separate thread
            threading.Thread(target=process_transcript, args=(data,)).start()

            return response, 200

        except Exception as e:
            print(f"Error processing webhook data: {str(e)}")
            # Even if there's an error, return a success response to prevent retries
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Error processing webhook data, but received",
                    }
                ),
                200,
            )

    else:
        print(f"Received non-handled method: {request.method}")
        return "Method not allowed", 405


if __name__ == "__main__":
    app.run(port=5000)
