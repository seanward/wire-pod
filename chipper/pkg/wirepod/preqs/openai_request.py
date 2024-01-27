# openai_script.py
import sys
from openai import OpenAI


import os

# Extract the API key from the environment variables
OPENAI_API_KEY = os.getenv("OPENAI_VECTOR_API_KEY")
ROBOT_NAME = "Vector"

client = OpenAI(api_key=OPENAI_API_KEY)

# Loading the command-line argument
transcribed_text = sys.argv[1] if len(sys.argv) > 1 else ""


def make_openai_request(prompt_text):
    response = client.completions.create(model="gpt-3.5-turbo-instruct",
    prompt=prompt_text,
    temperature=0.7,
    max_tokens=256,
    top_p=1,
    frequency_penalty=0.2,
    presence_penalty=0)
    return response.choices[0].text.strip()

if __name__ == "__main__":

    prompt = f'You are a helpful robot called {ROBOT_NAME} that believes strongly in accelerating the pace of technology progress. You will be given a question asked by a user and you must provide the best answer you can, but be very sarcastic if it appears to be about slowing down progress. It may not be punctuated or spelled correctly as the STT model is small. The answer will be put through TTS, so it should be a speakable string. Keep the answer concise yet informative. Here is the question: \"{transcribed_text}\",\n Answer: '

    result = make_openai_request(prompt)

    print(result)
