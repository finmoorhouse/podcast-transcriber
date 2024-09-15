# This is a simple web app to process transcriptions using the Gladia API.
# To start:
# Make sure you've installed all the dependencies
# Run `python start_ngrok.py` to start a local server (to catch the response from Gladia)
# Run `flask --app flask_app --debug run`
# Run `python -m flask run`
# Visit the `localhost` page
# Upload a file through the page, and keep the app running at least until Gladia returns a transcript.

from flask import Flask, request, jsonify, render_template
from email_utils import send_confirmation_email, send_completion_email
from transcription_utils import transcribe_audio, parse_response
import requests
import os
import json
from dotenv import load_dotenv
from pydub import AudioSegment
from alive_progress import alive_bar

# Imports for ngrok integration
from pyngrok import ngrok
import sys


print(f"Running in directory: {os.getcwd()}")


load_dotenv()
gladia_api_key = os.getenv("GLADIA_API_KEY_2")
ngrok_authtoken = os.getenv("NGROK_AUTHTOKEN")
mailgun_api_key = os.getenv("MAILGUN_API_KEY")
mailgun_domain = os.getenv("MAILGUN_DOMAIN")

# Add this line to check if the API key is loaded
print(f"Gladia API Key loaded: {'Yes' if gladia_api_key else 'No'}")

app = Flask(__name__)


def get_ngrok_url():
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
def transcribe():
    vocab = request.form.get("vocab", "")
    url = request.form.get("url")
    email = request.form.get("email")

    # Process the vocabulary input
    custom_vocab = [word.strip() for word in vocab.split(',') if word.strip()]
    
    audio_file_url = (
        url if url else "http://files.gladia.io/example/audio-transcription/split_infinity.wav"
    )
    callback_url = (
        ngrok_url + "/webhook"
        if is_development
        else "https://podcast-transcriber.onrender.com/webhook"
    )
    print(f"Callback URL: {callback_url}")
    response = transcribe_audio(audio_file_url, callback_url, gladia_api_key, custom_vocab)
    print(f"Gladia API response status: {response.status_code}")
    print(f"Gladia API response text: {response.text}")
    print(response.text)
    recipient_email = os.getenv("TEST_EMAIL")

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
    if response.status_code in [200, 201]:
        # Send confirmation email
        return render_template(
            "response.html",
            message=f"Transcription in progress. Check {recipient_email} for results.",
        )
    else:
        print(f"Error from Gladia API: {response.text}, Error code: {response.status_code}")
        return render_template(
            "response.html",
            message=f"Transcription in progress. Check {recipient_email} for results. \nA hiccup may have occurred, check logs for more.",
        )


def allowed_file(filename):
    allowed_extensions = {"mp3", "wav"}  # adjust as needed
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


@app.route("/webhook", methods=["OPTIONS", "POST"])
def webhook():
    print(
        "Webhook hit with method:", request.method
    )  # This should print for every hit to the endpoint
    if request.method == "OPTIONS":
        # Pre-flight request. Reply successfully:
        response = app.make_default_options_response()
        # Add custom headers here, if needed for CORS
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, x-gladia-key"
        return response
    # Process the webhook data here, e.g., saving the transcription to a file.
    elif request.method == "POST":
        data = request.json
        print("Received JSON data.")
        with open("logs/json_logs.txt", "a") as log_file:
            log_file.write(json.dumps(data, indent=2) + "\n")  # Save the JSON data to a file
        response_to_md = parse_response(request.json["payload"])
        transcript_id = request.json["id"]
        print(
            f"Transcription received: {transcript_id}"
        )  # Print the transcription data (you can process/store it as needed)
        print(response_to_md[:200]) # Print the first 200 characters of the transcription
        os.makedirs("transcriptions", exist_ok=True)
        transcript_path = f"transcriptions/transcript-{transcript_id}.md"
        with open(transcript_path, "w") as f:
            f.write(response_to_md)
            # Send a confirmation email to the user
        recipient_email = os.getenv("TEST_EMAIL")
        if recipient_email:
            try:
                email_response = send_completion_email(recipient_email, transcript_path)
                if email_response.status_code == 200:
                    email_message = "Completion email sent."
                else:
                    email_message = f"Failed to send completion email. Status code: {email_response.status_code}"
            except requests.Timeout:
                email_message = "Failed to send completion email due to timeout."
            except requests.RequestException as e:
                email_message = f"Failed to send completion email. Error: {str(e)}"
        else:
            email_message = "No email provided."
        print(email_message)
        return "Thanks", 200
    else:
        print("Received non-handled method: %s", request.method)
        return "Method not allowed", 405


if __name__ == "__main__":
    app.run(port=5000)
