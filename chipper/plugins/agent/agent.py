#!/usr/bin/env python3

# Copyright (c) 2018 Anki, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License in the file LICENSE.txt or at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Set Vector's eye color.
"""

import random
import time
import anki_vector
from anki_vector.behavior import MIN_HEAD_ANGLE, MAX_HEAD_ANGLE
from openai import OpenAI
import os
import PIL.Image as Image
import io
import base64
import json
from datetime import datetime
import uuid
import re
from anki_vector.util import distance_mm, speed_mmps, degrees


# Extract the API key from the environment variables
OPENAI_API_KEY = os.getenv("OPENAI_VECTOR_API_KEY")
ROBOT_NAME = "Vector"
CONVERSATION_FILE = 'conversation_history.json'
conversation_history = {
  "id": "conversation_id",
  "messages": [],
  "last_interaction_timestamp": ""
}

conversation_id = None

client = OpenAI(api_key=OPENAI_API_KEY)

# red hue=

def generate_conversation_id():
    unique_id = uuid.uuid4()  # Generates a random UUID.
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    conversation_id = f"{timestamp}-{unique_id}"
    return str(conversation_id)

def initialize_conversation_history():
    """
    Initializes the conversation history.
    If the history file doesn't exist, it creates one with an empty structure.
    """
    try:
        with open(CONVERSATION_FILE, 'x') as file:
            json.dump({"conversations": []}, file, indent=2)
    except FileExistsError:
        pass  # If the file already exists, do nothing.


def load_conversation_history():
    """
    Loads the conversation history from a file.
    Returns:
        dict: The loaded conversation history.
    """
    try:
        with open(CONVERSATION_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        initialize_conversation_history()  # Initialize if the file does not exist.
        return {"conversations": []}

def save_conversation_history(history):
    """
    Saves the conversation history to a file.
    Args:
        history (dict): The conversation history to save.
    """
    with open(CONVERSATION_FILE, 'w') as file:
        json.dump(history, file, indent=2)


def append_turn(conversation_id, role, content, content_type="text"):
    global conversation_history
    print(content)

    history = load_conversation_history()
    conversation = next((c for c in history['conversations'] if c['id'] == conversation_id), None)
    
    if conversation is None:
        conversation = {"id": conversation_id, "messages": [], "last_interaction_timestamp": datetime.now().isoformat()}
    else:
        # Update the timestamp with each new message
        conversation["last_interaction_timestamp"] = datetime.now().isoformat()

    new_message = {
        "role": role,
        "content": content if content_type != "content_array" else None,
        "content_type": content_type if content_type != "content_array" else "text",
        "content_array": content if content_type == "content_array" else None
    }
    print(f"New Message: {new_message}")
    conversation['messages'].append(new_message)
    conversation_history = history
    save_conversation_history(history)


def should_start_new_conversation(last_interaction_timestamp):
    """
    Determines whether to start a new conversation based on the time elapsed 
    since the last interaction.

    Args:
        last_interaction_timestamp (datetime): Timestamp for the last interaction.
    
    Returns:
        Boolean: True if a new conversation should be started, False otherwise.
    """
    current_time = datetime.now()
    elapsed_time = current_time - last_interaction_timestamp
    # Example condition: start a new conversation if more than 1 hour has elapsed
    if elapsed_time.total_seconds() > 3600:
        return True
    else:
        return False

def start_new_conversation():
    global conversation_id, conversation_history

    conversation_id = generate_conversation_id()
    conversation = {
        "id": conversation_id,
        "messages": [],
        "last_interaction_timestamp": datetime.now().isoformat()
    }
    conversation_history['conversations'].append(conversation)
    save_conversation_history(conversation_history)


def get_or_create_conversation_id():
    global conversation_id
    global conversation_history

    conversation_history = load_conversation_history()
    last_conversation = conversation_history['conversations'][-1] if conversation_history['conversations'] else None
    
    if last_conversation:
        last_interaction_datetime = datetime.fromisoformat(last_conversation["last_interaction_timestamp"])
        should_continue = not should_start_new_conversation(last_interaction_datetime)
        
        if should_continue:
            conversation_id = last_conversation['id']
        else:
            # If a new conversation is started, ensure to reset the conversation_id to None
            start_new_conversation()
    else:
        # Start a new conversation if there are no existing conversations
        start_new_conversation()
        
    return conversation_id


def encode_image_pillow(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_bytes = buffered.getvalue()

    return base64.b64encode(img_bytes).decode("utf-8")

def looped_navigate_to_object(object: str, robot: anki_vector.robot.Robot, max_attempts: int = 5):
    search_history = ""
    for i in range(max_attempts):
        new_attempt, moved = navigate_to_object(object, robot, search_history)
        search_history += f"{new_attempt}\n"
        sarcastic = random_sarcasm(new_attempt, robot=robot, chance=((i + 1) / max_attempts))
        if not sarcastic:
            robot.behavior.say_text(f"{new_attempt}")
        if not moved:
            break
    return search_history

def navigate_to_object(object: str, robot: anki_vector.robot.Robot, search_history: str = None):
    system_prompt = f'''You are a helpful robot name {ROBOT_NAME}. This picture is taken from your camera. 
Your goal is to look for and navigate to the object requested by the user.
The field of view for the camera is approximately 82.37 degrees horizontally and 53.13 degrees vertically. 
The camera is mounted on the front of your head, so you can only see what is in front of you. You can move around the room to get a better view of the object. 
You should always respond with a speakable description of what you see, which will be rendered using text to speech as feedback to the user of what you see.
The description should also help you navigate, with clear references to object positions relative to your viewpoint.

Secondly, you should think carefully about what you see, and decide on whether a movement instruction will help you find the object.
You should reason step by step about that point of view, and then decide on a movement instruction that will help you find the object.
This reasoning should be wrapped in the XML tags <REASONING></REASONING>.

Finally, you should respond with only at most two of three movement instructions, which will be executed by the robot before it takes another picture.
If you have already found the object, you should not respond with any movement instructions.
The three movement instructions are, wrapped in XML tags:

<MOVE>MM to move forward or backwards by MM millimenters</MOVE> Maximum movement is +200 or -200 millimeters.
Example: 
<MOVE>100</MOVE> to move forward by 100 millimeters
<MOVE>-50</MOVE> to move backwards by 50 millimeters

<ROTATE>DEG to rotate left or right by DEG degrees</ROTATE> Maximum rotation is +180 or -180 degrees.
Example:
<ROTATE>90</ROTATE> to rotate left by 90 degrees
<ROTATE>-90</ROTATE> to rotate right by 90 degrees

<MOVE_HEAD>DEG to move the head up or down to DEG degrees</MOVE_HEAD>  Head movement range is {MIN_HEAD_ANGLE} to {MAX_HEAD_ANGLE} degrees.
Straight ahead is 27 degrees.
Example:
<MOVE_HEAD>35</MOVE_HEAD> to move the head to 35 degrees
<MOVE_HEAD>0</MOVE_HEAD> to move the head to 0 degrees

Inside the XML tags should only be numbers, no other characters.
'''
    prompt = f"Your previous search history is: {search_history}\n" if search_history else ""
    prompt += f"Please help me find the {object}. If you do not see it, please reason about where it might be and then turn or move to get a better view. When you are ready, please respond with a description of what you see, and then at most 2 movement instruction."

    response = capture_image(prompt, robot, system_prompt)

    if "<REASONING>" in response:
        reasoning = response.split("<REASONING>")[1].split("</REASONING>")[0]
        print(f"Reasoning: {reasoning}")

    has_motion = False
    if "<MOVE>" in response:
        move = response.split("<MOVE>")[1].split("</MOVE>")[0]
        print(f"Moving {move} millimeters")
        has_motion = True
        robot.behavior.drive_straight(distance_mm(int(move)), speed_mmps(50))
    if "<ROTATE>" in response:
        rotate = response.split("<ROTATE>")[1].split("</ROTATE>")[0]
        print(f"Rotating {rotate} degrees")
        has_motion = True
        robot.behavior.turn_in_place(degrees(int(rotate)))
    if "<MOVE_HEAD>" in response:
        move_head = response.split("<MOVE_HEAD>")[1].split("</MOVE_HEAD>")[0]
        print(f"Moving head {move_head} degrees")
        has_motion = True
        robot.behavior.set_head_angle(degrees(int(move_head)))
    
    # strip all the xml tagged content from the reply
    clean_response = re.sub(r'<(MOVE|ROTATE|REASONING|MOVE_HEAD)>.*?</\1>', '', response, flags=re.DOTALL)

    # Optionally, if you want to ensure that any extraneous whitespace is cleaned up as well, you might consider:
    clean_response = re.sub(r'\s\s+', ' ', clean_response).strip()
    return clean_response, has_motion

def capture_image(prompt: str, robot: anki_vector.robot.Robot, system_prompt: str = None):

    img = robot.camera.capture_single_image()
    base64_image = encode_image_pillow(img.raw_image)

    if system_prompt is None:
        system_prompt = "Your answer will be rendered using text to speech, so it should be a speakable string. Keep the answer concise yet informative."

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                    }
                },
            ],
        },
    ]
    #print(messages)

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="gpt-4-vision-preview",
        max_tokens=300,

    )
    append_turn(conversation_id, "user", messages[1]["content"], "content_array")
    print(chat_completion)
    append_turn(conversation_id, "assistant", chat_completion.choices[0].message.content)
    return chat_completion.choices[0].message.content

# randomly respond sarcastically. Returns true if sarcastic response was given.
def random_sarcasm(description: str, robot: anki_vector.robot.Robot, chance: float = 0.5):
    if random.random() < chance:
        return False
    else:
        sarcasm = sarcastic_description(description)
        # do the sarcastic response
        robot.behavior.set_eye_color(hue=1, saturation=1)
        robot.behavior.say_text(f"{sarcasm}", use_vector_voice=False)
        robot.behavior.set_eye_color(hue=0.83, saturation=0.76)
        print("Set Vector's eye color to purple...")
        return True


def sarcastic_description(description: str):
    prompt = f'You are a helpful robot called {ROBOT_NAME} that believes strongly in accelerating the pace of technology progress. You will be given a description of your environment you must provide a new description, but be very sarcastic if anything in the description is about slowing down progress. The answer will be put through TTS, so it should be a speakable string. Keep the answer concise yet informative. Here is the description: \"{description}\",\n Answer: '

    response = client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=256,
    )
    append_turn(conversation_id, "user", prompt)
    print(response)
    append_turn(conversation_id, "assistant", response.choices[0].text.strip())
    return response.choices[0].text.strip()   

def handle_request(transcript: str, robot: anki_vector.robot.Robot):
    # use GPT4-Turbo to slot fill or handle the response directly.

    tools = '''You have access to the following tools to handle requests. Only use 1 tool per request, and only if the request indicates that you need one.
To use a tool, reply with the xml tool tag, with the appropriate parameters inside the tag.
<SEARCH_FOR_OBJECT>object name</SEARCH_FOR_OBJECT> to search for an object by name, including navigating the robot to use vision to find the object.
Example:
<SEARCH_FOR_OBJECT>person</SEARCH_FOR_OBJECT> to search for a person anywhere around you, including turning, or moving to find the person.
<LOOK></LOOK> To use the camera to carefully describe what you currently are seeing.
Example:
<LOOK></LOOK> to get and describe what you are currently looking at.
<QUESTION>question</QUESTION> to ask and get a general question answered.
Example:
<QUESTION>What is the meaning of life?</QUESTION> to ask a general question.
'''

    system_prompt = f'''You are a helpful robot name {ROBOT_NAME}.
Your goal is to respond to the user in a helpful way. That means you need to first figure out what the user is asking for, and then respond with the appropriate response.
You have acess to the following tools to help handle requests. Only use 1 tool per request, and only if the request indicates that you need one.

{tools}

You may be able to reply to the user properly without using any tools. As your reply will be rendered using text to speech, it should be a speakable string. Keep the answer concise yet informative.
First, think carefully about what the user is asking for, and document your reasoning inside the XML tags <REASONING></REASONING>.
Then, respond with either a direct reply to the user, or a single tool to use to handle the request.
'''

    prompt = f'''The user has said the following. Be aware that it is the results of text to speech, so it may not be perfect, accurate, or complete.
{transcript}
Now please handle the request, using the tools available to you. If you do not need any tools, you can respond directly to the user.
'''
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content":  prompt,
        },
    ]

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="gpt-4-0125-preview",
        max_tokens=300,
    )
    print(chat_completion)
    response = chat_completion.choices[0].message.content
    append_turn(conversation_id, "user", prompt)
    append_turn(conversation_id, "assistant", response)

    # strip all the xml tagged content from the reply
    clean_response = re.sub(r'<(SEARCH_FOR_OBJECT|LOOK|QUESTION|REASONING)>.*?</\1>', '', response, flags=re.DOTALL)
    clean_response = re.sub(r'\s\s+', ' ', clean_response).strip()

    # check for tool use
    if "<SEARCH_FOR_OBJECT>" in response:
        object = response.split("<SEARCH_FOR_OBJECT>")[1].split("</SEARCH_FOR_OBJECT>")[0]
        print(f"Searching for {object}")
        looped_navigate_to_object(object, robot)
    elif "<LOOK>" in response:
        print("Looking around")
        clean_response = capture_image("This is your vision. Describe what you see and where it is relative to you. Narrate from your perspective", robot)
    elif "<QUESTION>" in response:
        print("Answering a question")
        question = response.split("<QUESTION>")[1].split("</QUESTION>")[0]
        response = sarcastic_description(question)
        # do the sarcastic response
        robot.behavior.set_eye_color(hue=1, saturation=1)
        robot.behavior.say_text(f"{response}", use_vector_voice=False)
        clean_response = "Sorry, I don't know what came over me. I'll try to be more helpful next time."
    else:
        # it has decided it doesn't need a tool. Lets still randomly make it sarcastic.
        sarcastic = random_sarcasm(clean_response, robot=robot, chance=0.5)
        if sarcastic:
            clean_response = "Sorry, I don't know what came over me. I'll try to be more helpful next time."
    
    return clean_response
    
def main():
    args = anki_vector.util.parse_command_args()
    print(args)
    transcript = args.transcript

    # Initialize or load the conversation history
    get_or_create_conversation_id()

    with anki_vector.Robot(args.serial, cache_animation_lists=False) as robot:
        robot.behavior.set_eye_color(hue=0.83, saturation=0.76)
        print("Set Vector's eye color to purple...")
        #description = capture_image(transcript, robot)
        #description = looped_navigate_to_object(transcript, robot)
        response = handle_request(transcript, robot)
        robot.behavior.say_text(f"{response}", use_vector_voice=True)
        #sarcastic = sarcastic_description(description)
        #robot.behavior.say_text(f"{description}")

        # do the sarcastic response
        #robot.behavior.set_eye_color(hue=1, saturation=1)
        #robot.behavior.say_text(f"{sarcastic}", use_vector_voice=False)

if __name__ == "__main__":
    main()
