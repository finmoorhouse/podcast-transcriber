import requests
from dotenv import load_dotenv
import os
import json
from pydub import AudioSegment
from alive_progress import alive_bar


load_dotenv()
gladia_api_key = os.getenv("GLADIA_API_KEY")
headers = {
    # Accept json as a response, but we are sending a Multipart FormData
    'accept': 'application/json',
    'x-gladia-key': gladia_api_key
}

file_path = input("Please enter the path to the audio file: ").strip("'")  # Change with your file path

def format_duration(seconds):
    """Convert duration in seconds to a formatted string: HH:MM:SS."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))


if os.path.exists(file_path):  # This is here to check if the file exists
    print("📁 File found")
    # Display spinner while processing
    with alive_bar(1, spinner="waves", bar=None, title="Loading audio file.", monitor = None, stats = None, elapsed = "{elapsed} seconds elapsed.") as bar:
        # Load audio file
        audio = AudioSegment.from_file(file_path)
        bar()
    # Get and print the length of the audio file
    audio_length = audio.duration_seconds
    formatted_duration = format_duration(audio_length)
    print(f"Audio duration: {formatted_duration}")
else:
    print("🔴 File not found. Exiting program.")
    exit()

file_name, file_extension = os.path.splitext(file_path)  # Get your audio file name + extension


def send_to_api(current_file_path, chunk_current, chunk_total):
    with open(current_file_path, 'rb') as f:  # Open the file
        files = {
            # Send the local audio file. Here it represents: (filename: string, file: BufferReader, fileMimeType: string)
            'audio': (file_name, f, 'audio/'+file_extension[1:]),
            'toggle_diarization': (None, True),
            'language': "english",
            'transcription_hint': "This is a transcription hint.",
            'webhook_url' : "(Replce with actual webhook URL)"
        }
        print(f"📡 Sending chunk number {chunk_current} of {chunk_total} to Gladia API...")
        with alive_bar(1, spinner="waves", bar=None, title="Processing transcript.", monitor = None, stats = None, elapsed = "{elapsed} seconds elapsed.") as bar:
            response = requests.post('https://api.gladia.io/audio/text/audio-transcription/', headers=headers, files=files)
            bar()
        if response.status_code == 200:
            print("Request successful.")
        else:
            print('🔴 Request failed')
            print(response.json())
            exit()
        return response
    

# Extract the first 4 minutes
chunk_length = 120 * 60 * 1000  # In milliseconds. The first number is the number of minutes.
num_chunks = int((audio_length * 1000) // chunk_length) + (1 if (audio_length * 1000) % chunk_length else 0)

all_responses = []

for i in range(num_chunks):
        start_time = i * chunk_length
        end_time = (i + 1) * chunk_length
        chunk = audio[start_time:end_time]
        
        # Save to a temporary file
        temp_file_path = f"temp_audio_segment_{i}" + file_extension
        chunk.export(temp_file_path, format=file_extension[1:])
        
        response = send_to_api(temp_file_path,i+1,num_chunks)
        if response:
            all_responses.append(response)
        
        # Remove the temporary file
        os.remove(temp_file_path)


# with open("raw_response.md", "w") as f:
#     f.write(json.dumps(response.json(), indent=4))


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
    segments = data['prediction']
    for segment in segments:
        speaker_id = str(segment.get('speaker'))

        # If we have a change in speaker or it's the last segment
        if current_speaker is not None and (current_speaker != speaker_id or segment == segments[-1]):
            markdown_output.append(f"\n\n**[SPEAKER {speaker_id}]**\n")
            markdown_output.append(" ".join(speaker_text))
            # Reset for the next speaker
            speaker_text = []

        current_speaker = speaker_id
        speaker_text.append(segment['transcription'])

    # Handling the text for the last segment
    if speaker_text:
        markdown_output.append(" ".join(speaker_text))

    # Return the markdown transcript
    return "\n".join(markdown_output)

#parsed_response = parse_response(response.json())

# Aggregate all responses
all_parsed_responses = []

for resp in all_responses:
    parsed_resp = parse_response(resp.json())
    all_parsed_responses.append(parsed_resp)

# Combine the parsed responses
combined_responses = "\n\n[NEW CHUNK]\n".join(all_parsed_responses)

with open("transcript-py-test.md", "w") as f:
    f.write(combined_responses)
    print("💾 File saved to markdown.")