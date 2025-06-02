import os
import time
from typing import List
import requests
from dotenv import load_dotenv
import re
from openai import OpenAI, RateLimitError
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def transcribe_audio_file_requests(
    audio_file, callback_url, deepgram_api_key, custom_vocab
):
    """Transcribe an audio file using the Deepgram API and the requests library."""
    # Define the URL for the Deepgram API endpoint
    url = "https://api.deepgram.com/v1/listen"

    # Define the headers for the HTTP request
    headers = {"Authorization": f"Token {deepgram_api_key}", "Content-Type": "audio/*"}

    # Define query parameters
    params = {
        "callback": callback_url,
        "diarize": "true",
        "smart_format": "true",
        "model": "nova-2",
    }

    # Add custom vocabulary if provided
    if custom_vocab:
        params["keywords"] = ",".join(custom_vocab)

    response = requests.post(url, headers=headers, params=params, data=audio_file, timeout=1000)
    print(response)
    return response


def parse_response(json_response):
    """Parse the JSON response and return a markdown-formatted transcript."""
    segments = json_response["results"]["channels"][0]["alternatives"][0]["paragraphs"]
    # Variables to keep track of ongoing speaker and their text
    markdown_output = []
    current_speaker = None
    speaker_text = []
    paragraphs = segments["paragraphs"]
    for paragraph in paragraphs:
        speaker_id = str(paragraph["speaker"])
        # If we have a change in speaker or it's the last paragraph
        if current_speaker is not None and (
            current_speaker != speaker_id or paragraph == paragraphs[-1]
        ):
            markdown_output.append(f"\n\n**[SPEAKER {speaker_id}]**: ")
            markdown_output.append(" ".join(speaker_text))
            # Reset for the next speaker
            speaker_text = []
        current_speaker = speaker_id
        # Concatenate all sentences in the paragraph
        paragraph_text = " ".join(
            sentence["text"] for sentence in paragraph["sentences"]
        )
        speaker_text.append(paragraph_text)
    # Handling the text for the last segment
    if speaker_text:
        markdown_output.append(" ".join(speaker_text))

    full_transcript = "\n".join(markdown_output)
    # Return the markdown transcript
    # return full_transcript
    # Save the full transcript to a file
    with open("transcription_test.md", "w") as f:
        f.write("Transcript before formatting:\n\n" + full_transcript)
    return post_process_transcript(full_transcript)


def post_process_transcript(transcript: str) -> str:
    """
    Post-process a transcript by splitting it into chunks and processing each chunk with GPT-4.

    Args:
        transcript (str): The input transcript to be processed.

    Returns:
        str: The processed transcript.
    """
    sentences = split_into_sentences(transcript)
    chunks = create_chunks(sentences)

    processed_chunks = []

    for chunk in chunks:
        processed_chunk = process_chunk_with_gpt4(chunk)
        processed_chunks.append(processed_chunk)

    return "\n\n".join(processed_chunks)


def split_into_sentences(text: str) -> List[str]:
    """
    Split the text into sentences, preserving speaker labels and line breaks.

    Args:
        text (str): The input text to be split.

    Returns:
        List[str]: A list of sentences.
    """
    # Split by newlines first to preserve speaker labels and line breaks
    lines = text.split('\n')
    sentences = []
    for line in lines:
        if line.strip().startswith('**[SPEAKER'):
            sentences.append(line)
        elif line.strip() == '':
            sentences.append('\n')  # Preserve empty lines
        else:
            # Use regex to split into sentences
            line_sentences = re.split(r'(?<=[.!?])\s+', line)
            sentences.extend(line_sentences)
    return [s for s in sentences if s]  # Remove empty strings but keep '\n'


def create_chunks(sentences: List[str], max_tokens: int = 600) -> List[str]:
    """
    Create chunks of sentences that fit within the max_tokens limit.

    Args:
        sentences (List[str]): List of sentences to be chunked.
        max_tokens (int): Maximum number of tokens per chunk.

    Returns:
        List[str]: A list of chunks.
    """
    chunks = []
    current_chunk = []
    current_token_count = 0

    for sentence in sentences:
        sentence_tokens = len(sentence.split())
        if current_token_count + sentence_tokens > max_tokens:
            chunks.append("".join(current_chunk))
            current_chunk = []
            current_token_count = 0

        current_chunk.append(sentence)
        current_token_count += sentence_tokens

    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks


def process_chunk_with_gpt4(chunk):
    """
    Process a chunk of text with GPT-4.

    Args:
        chunk (str): The chunk of text to be processed.

    Returns:
        str: The processed chunk of text.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Processing chunk: {chunk[:200]}...")
            response = client.chat.completions.create(
                model="gpt-4o-2024-11-20",  # Updated to a standard GPT-4 model
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI assistant that receives a verbatim transcript of an interview. You respond with the same text, MINIMALLY edited for clarity. You remove filler words, correct grammatical mistakes, and replace obvious transcription mistakes with the more likely alternative given the context. You remove obvious repetition. If a line from a speaker is just filler, such as '[Spaker 0]: Mhmm.', then you can just delete the line as if the speaker never interrupted. You add links in markdown format to resources mentioned where you are confident of the link (so 'World Health Organisation' could become '[World Health Organisation](https://www.who.int/)'). When a speaker appears to start talking about a new topic, add a markdown-formated h3 header (### [Topic]) before the next speaker is introduced in bold, replacing [Topic] with the actual new topic. The speaker name (e.g. '[SPEAKER 0]:') should precede the speaker text without a line break. You DO NOT invent any new sentences. You DO NOT modify the speaker names in bold. You DO NOT remove any substantial content and you DO NOT summarise answers — the transcript you return should effectively be as long as the original, minus filler words and obvious repetition. You don't need to make speech less casual than it already is. The text should be returned in just the same format as it was received.",
                    },
                    {"role": "user", "content": chunk},
                ],
                max_tokens=5000,
                n=1,
                temperature=0.5,
            )

            if response.choices and len(response.choices) > 0:
                processed_chunk = response.choices[0].message.content.strip()
                print(f"Processed chunk: {processed_chunk[:200]}...")
                return processed_chunk
            else:
                print(f"Unexpected response structure: {response}")
                return None
        except Exception as e:
            if isinstance(e, RateLimitError) and attempt < max_retries - 1:
                time.sleep(2**attempt)  # Exponential backoff
            else:
                print(f"Error processing chunk: {e}")
                return None
