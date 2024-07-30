# This is a simple web app to process transcriptions using the Gladia API.

# To start:

# Make sure you've installed all the dependencies
# - Run `ngrok http 5000` to start a local server (to catch the response from Gladia)
# - Run `flask --app flask-app run`
# For some reason `flask --app flask-app --debug run` gets an ngrok error.
# - Visit the `localhost` page (for me it's `http://127.0.0.1:5000`)
# - Upload a file through the page, and keep the app running at least until Gladia returns a transcript.

from flask import Flask, request, jsonify, render_template

import requests
import os
from dotenv import load_dotenv
from pydub import AudioSegment
from alive_progress import alive_bar

# Imports for ngrok integration
from pyngrok import ngrok
import sys


print(f"Running in directory: {os.getcwd()}")


load_dotenv()
gladia_api_key = os.getenv("GLADIA_API_KEY")
ngrok_authtoken = os.getenv("NGROK_AUTHTOKEN")
mailgun_api_key = os.getenv("MAILGUN_API_KEY")
mailgun_domain = os.getenv("MAILGUN_DOMAIN")
headers = {
    # Accept json as a response, but we are sending a Multipart FormData
    "accept": "application/json",
    "x-gladia-key": gladia_api_key,
}

app = Flask(__name__)


# Function to get ngrok tunnel URL
def get_ngrok_url():
    try:
        ngrok.set_auth_token(ngrok_authtoken)
        tunnels = ngrok.get_tunnels()
        if tunnels:
            return tunnels[0].public_url
        else:
            ngrok_tunnel = ngrok.connect(5000)
            return ngrok_tunnel.public_url
    except Exception as e:
        print(f"Error setting up ngrok: {e}")
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


def split_audio(audio_file):
    # Define the parameters
    segment_length = 1 * 3600000  # Time in hours times milliseconds in an hour

    # Load the audio file
    with alive_bar(
        1,
        spinner="waves",
        bar=None,
        title="Loading audio file.",
        monitor=None,
        stats=None,
        elapsed="{elapsed} seconds elapsed.",
    ) as bar:
        # Load audio file
        audio = AudioSegment.from_file(audio_file)
        bar()

    # Split the audio file into fixed-length chunks
    chunks = []
    with alive_bar(
        1,
        spinner="waves",
        bar=None,
        title="Splitting audio file.",
        monitor=None,
        stats=None,
        elapsed="{elapsed} seconds elapsed.",
    ) as bar:
        for i in range(0, len(audio), segment_length):
            chunk = audio[i : i + segment_length]
            chunks.append(chunk)
        bar()
    print(f"Number of chunks: {len(chunks)}")
    return chunks


def send_confirmation_email(recipient_email):
    mailgun_domain = os.getenv("MAILGUN_DOMAIN")
    mailgun_api_key = os.getenv("MAILGUN_API_KEY")

    url = f"https://api.mailgun.net/v3/{mailgun_domain}/messages"
    
    data = {
        "from": f"Transcription Service <mailgun@{mailgun_domain}>",
        "to": [recipient_email],
        "subject": "Transcription Request Received",
        "text": "Your transcription request has been received and is being processed. We'll notify you when it's complete.",
    }
    
    print(f"Sending email to {recipient_email}")
    print(f"Using Mailgun URL: {url}")
    print(f"Request data: {data}")
    
    try:
        response = requests.post(
            url,
            auth=("api", mailgun_api_key),
            data=data,
            timeout=10
        )
        print(f"Mailgun API response status: {response.status_code}")
        print(f"Mailgun API response text: {response.text}")
        return response
    except requests.RequestException as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        raise

@app.route("/transcribe", methods=["POST"])
def transcribe():
    # audio_url = request.form.get('audio_url')
    # print(f"Audio URL from form: {audio_url}")
    audio_file = request.files.get("audio_file")
    api_endpoint = "https://api.gladia.io/audio/text/audio-transcription/"
    prompt = request.form.get("prompt")
    recipient_email = request.form.get("email")
    if not prompt:
        prompt = ""
    if audio_file and allowed_file(audio_file.filename):
        # Split the audio file into chunks
        chunks = split_audio(audio_file)
        for index, chunk in enumerate(chunks):
            file_name = f"chunk_{index}.mp3"
            with alive_bar(
                1,
                spinner="waves",
                bar=None,
                title=f"Re-exporting audio file {index + 1} of {len(chunks)}.",
                monitor=None,
                stats=None,
                elapsed="{elapsed} seconds elapsed.",
            ) as bar:
                chunk.export(file_name)
                bar()

            with alive_bar(
                1,
                spinner="waves",
                bar=None,
                title=f"Uploading audio file {index + 1} of {len(chunks)}.",
                monitor=None,
                stats=None,
                elapsed="{elapsed} seconds elapsed.",
            ) as bar:
                with open(file_name, "rb") as f:
                    files = {
                        # Send the local audio file. Here it represents: (filename: string, file: BufferReader, fileMimeType: string)
                        #'audio_url': audio_url,
                        "audio": (file_name, f, "audio/mp3"),
                        "toggle_diarization": (None, True),
                        "language_behaviour": "manual",
                        "toggle_direct_translate": "false",
                        "language": "english",
                        "transcription_hint": prompt,
                        "webhook_url": (
                            ngrok_url + "/webhook"
                            if is_development
                            else "https://podcast-transcriber.onrender.com/webhook"
                        ),
                    }
                    # Send a POST request to the transcription API
                    response = requests.post(api_endpoint, headers=headers, files=files)
                    bar()
            # Clean up: remove the chunk file after sending it
            os.remove(file_name)
            if index > 2:
                break

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
        if response.status_code == 200:
            # Send confirmation email
            return render_template(
                "response.html",
                message="Transcription in progress. Please check your webhook endpoint for results.",
            )
        else:
            return render_template(
                "response.html",
                message=f"Error sending transcription request. Received response: {response.text}.",
            )
    else:
        return render_template(
            "response.html", message="Looks like you didn't upload a valid file."
        )


def allowed_file(filename):
    allowed_extensions = {"mp3", "wav"}  # adjust as needed
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def parse_response(json_response):
    # Parse the JSON string
    if isinstance(json_response, str):
        print("🔧 Response is a string and needed to be parsed as a json first.")
        data = json.loads(json_response)
    else:
        data = json_response

    markdown_output = []
    # Variables to keep track of ongoing speaker and their text
    current_speaker = None
    speaker_text = []

    # Extract the transcriptions from the predictions
    segments = data["prediction"]
    # timestamp = str(segments[0].get('time_begin'))
    # markdown_output.append(f"Beginning at {timestamp}.\n")

    for segment in segments:
        speaker_id = str(segment.get("speaker"))

        # If we have a change in speaker or it's the last segment
        if current_speaker is not None and (
            current_speaker != speaker_id or segment == segments[-1]
        ):

            markdown_output.append(f"\n\n**[SPEAKER {speaker_id}]**\n")
            markdown_output.append(" ".join(speaker_text))
            # Reset for the next speaker
            speaker_text = []

        current_speaker = speaker_id
        speaker_text.append(segment["transcription"])

    # Handling the text for the last segment
    if speaker_text:
        markdown_output.append(" ".join(speaker_text))

    # Return the markdown transcript
    return "\n".join(markdown_output)


@app.route("/webhook", methods=["OPTIONS", "POST"])
def webhook_endpoint():
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
        response_to_md = parse_response(request.json["payload"])
        transcript_id = request.json["request_id"]
        print(
            f"Transcription received: {transcript_id}"
        )  # Print the transcription data (you can process/store it as needed)
        print(response_to_md)
        os.makedirs("transcriptions", exist_ok=True)
        with open(f"transcriptions/transcript-{transcript_id}.md", "w") as f:
            f.write(response_to_md)
        return "Thanks", 200
    else:
        app.logger.warning("Received non-handled method: %s", request.method)
        return "Method not allowed", 405


if __name__ == "__main__":
    app.run(port=5000)
