import requests
import json
from openai import OpenAI
client = OpenAI()
import time
import os
from dotenv import load_dotenv

load_dotenv()

client.api_key = os.getenv("OPENAI_API_KEY")


def transcribe_audio(audio_file_url, callback_url, gladia_api_key, custom_vocab):
    print(f"Your API key is: {gladia_api_key[0:10]}...")
    api_endpoint = "https://api.gladia.io/v2/transcription"

    payload = {
        "context_prompt": "Return the transcription in complete clear sentences, without filler words.",
        "custom_vocabulary": custom_vocab if custom_vocab else [],
        "detect_language": False,
        "enable_code_switching": False,
        "language": "en",
        "callback_url": callback_url,
        "diarization": True,
        "audio_url": audio_file_url,
    }
    headers = {
        "x-gladia-key": gladia_api_key,
        "Content-Type": "application/json",
    }
    try:
        print(f"Sending request to Gladia API with headers: {headers}")
        print(f"Payload: {payload}")
        response = requests.post(
            api_endpoint, json=payload, headers=headers, timeout=100
        )
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.text}")
        return response
    except requests.Timeout:
        print("Request timed out.")
        return None


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
    segments = data["transcription"]["utterances"]

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
        speaker_text.append(segment["text"])

    # Handling the text for the last segment
    if speaker_text:
        markdown_output.append(" ".join(speaker_text))

    full_transcript = "\n".join(markdown_output)
    # Return the markdown transcript
    return post_process_transcript(full_transcript)


def post_process_transcript(transcript):
    chunks = split_transcript(transcript)
    processed_chunks = []

    for chunk in chunks:
        processed_chunk = process_chunk_with_gpt4(chunk)
        processed_chunks.append(processed_chunk)

    return "\n\n".join(processed_chunks)


def split_transcript(transcript, max_tokens=3000):
    chunks = []
    current_chunk = []
    current_token_count = 0

    for line in transcript.split("\n"):
        line_tokens = len(line.split())
        if current_token_count + line_tokens > max_tokens:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_token_count = 0

        current_chunk.append(line)
        current_token_count += line_tokens

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks



def process_chunk_with_gpt4(chunk):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Processing chunk: {chunk}")
            response = client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",  # Updated to match your model
                messages=[
                    {"role": "system", "content": "You are an AI assistant that receives a verbatim transcript of an interview. You respond with the same text, lightly edited for clarity. You remove filler words, correct grammatical mistakes, and replace obvious transcription mistakes with the more likely alternative given the context. You remove obvious repetition. You add links in markdown format to resources mentioned where you are confident of the link (so 'World Health Organisation' could become '[World Health Organisation](https://www.who.int/)'). When an obvious new topic is introduced, you may add a markdown-formated h3 header (### Topic) before the next speaker is introduced in bold. You DO NOT invent any new sentences. You do NOT modify the speaker names in bold. The text should be returned in just the same format as it was received."},
                    {"role": "user", "content": chunk}
                ],
                max_tokens=4000,
                n=1,
                temperature=0.5,
            )
            
            if response.choices and len(response.choices) > 0:
                print(f"Response: {response.choices[0].message.content.strip()}")
                return response.choices[0].message.content.strip()
            else:
                print(f"Unexpected response structure: {response}")
                return None
        except client.RateLimitError:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"Rate limit exceeded after {max_retries} attempts.")
                return None
        except Exception as e:
            print(f"Error processing chunk: {e}")
            return None
