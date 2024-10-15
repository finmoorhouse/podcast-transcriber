
import os
import requests

def send_confirmation_email(recipient_email):
    """
    Sends a confirmation email to the recipient.

    Args:
        recipient_email (str): The email address of the recipient.

    Returns:
        requests.Response: The response from the email API.
    """
    mailgun_domain = os.getenv("MAILGUN_DOMAIN")
    mailgun_api_key = os.getenv("MAILGUN_API_KEY")

    url = f"https://api.eu.mailgun.net/v3/{mailgun_domain}/messages"

    data = {
        "from": f"Transcription Service <noreply@{mailgun_domain}>",
        "to": [recipient_email],
        "subject": "Transcription Request Received",
        "text": "Your transcription request has been received and is being processed. We'll notify you when it's complete.",
    }

    print(f"Sending email to {recipient_email}")
    print(f"Using Mailgun URL: {url}")
    print(f"Request data: {data}")

    try:
        response = requests.post(
            url, auth=("api", mailgun_api_key), data=data, timeout=10
        )
        print(f"Mailgun API response status: {response.status_code}")
        print(f"Mailgun API response text: {response.text}")
        return response
    except requests.RequestException as e:
        print(f"Error sending email: {str(e)}")
        raise


def send_completion_email(recipient_email, transcript_path):
    """
    Sends an email to the recipient with the completed transcript.

    Args:
        recipient_email (str): The email address of the recipient.

    Returns:
        requests.Response: The response from the email API.
    """
    mailgun_domain = os.getenv("MAILGUN_DOMAIN")
    mailgun_api_key = os.getenv("MAILGUN_API_KEY")

    url = f"https://api.eu.mailgun.net/v3/{mailgun_domain}/messages"

    data = {
        "from": f"Transcription Service <mailgun@{mailgun_domain}>",
        "to": [recipient_email],
        "subject": "Transcription Request Complete",
        "text": "Your transcription is ready, and you should find it as an attachment.\n\nThank you for using Podcast Transcripter!",
        #"attachment": (transcript_path, open(transcript_path, "rb")),
    }
    files = [("attachment", ("transcript.md", open(transcript_path, "rb")))]
    print(f"Sending email to {recipient_email}")
    print(f"Using Mailgun URL: {url}")
    print(f"Request data: {data}")

    try:
        response = requests.post(
            url, auth=("api", mailgun_api_key), data=data, files=files, timeout=10
        )
        print(f"Mailgun API response status: {response.status_code}")
        print(f"Mailgun API response text: {response.text}")
        return response
    except requests.RequestException as e:
        print(f"Error sending email: {str(e)}")
        raise
