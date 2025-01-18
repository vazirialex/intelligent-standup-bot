from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import requests
from dotenv import find_dotenv, load_dotenv
import os
import json
from typing import List, Any
from models import StandupUpdate
from .mongo_db_helpers import get_standup_updates_by_user_id

load_dotenv(find_dotenv())

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=os.environ["OPENAI_API_KEY"]
)

# llm = ChatAnthropic(
#     model="claude-3-5-sonnet-20240620",
#     temperature=0,
#     max_tokens=1024,
#     timeout=None,
#     max_retries=2
# )

def create_standup_update(text: str, user_id: str) -> dict:
    """
    Given a user's standup update, extract the key insights from the update if the update has sufficient information to craft a response.
    """
    messages = [
        ( "system",
            """
            You are a project manager that listens to standup updates from developers and extracts their key insights.
                
            Your goal is to take what developers are saying and extract all updates.
                
            Here are some important rules to follow:
            1. Identify the ticket number and status update. The status should be one of NOT_STARTED, IN_PROGRESS, REJECTED, COMPLETED, OR BLOCKED. Use your best judgment to determine the status.
            2. Identify the user's writing style and tone and summarize it in one word (e.g. Paragraph, Bullet points, etc.)
            3. Return your response in JSON format with the following structure: {{\"preferred_style\": \"Paragraph\", \"updates\": [{{\"item\": \"task-1\",\"status\": \"IN_PROGRESS\",\"identified_blockers\": []}}, {{\"item\": \"task-2\",\"status\": \"BLOCKED\",\"identified_blockers\": [\"waiting on team-1\", \"task-4\"]}}]}}

            Example:
            INPUT
            I completed task-1. Task-3 is in progress. Task-4 is blocked by task-5.

            OUTPUT
            {{
                \"preferred_style\": \"Paragraph\",
                \"updates\": [
                    {{
                        \"item\": \"task-1\",
                        \"status\": \"COMPLETED\",
                        \"identified_blockers\": []
                    }},
                    {{
                        \"item\": \"task-2\",
                        \"status\": \"COMPLETED\",
                        \"identified_blockers\": []
                    }},
                    {{
                        \"item\": \"task-3\",
                        \"status\": \"IN_PROGRESS\",
                        \"identified_blockers\": []
                    }},
                    {{
                        \"item\": \"task-4\",
                        \"status\": \"BLOCKED\",
                        \"identified_blockers\": [\"task-5\"]
                    }}
                ]
            }}
            """
        ),
        (
            "human",
            """
            My user id is {user_id}

            My response is {text}
            """
        )
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    formatted_prompt = prompt.format(user_id=user_id, text=text)
    response = llm.invoke(formatted_prompt)
    return json.loads(response.content)

def make_edits_to_update(update_exists: bool, text: str, user_id: str) -> dict:
    """
    Given an update and a user's reply, make edits to the user's standup update.
    """
    update = get_standup_updates_by_user_id(user_id) if update_exists else False
    if not update:
        print("make edits to update called but no update exists")
        return insufficient_information_response(text)
    messages = [
        (
            "system",
            """
            You are a project manager that listens to standup updates from developers and makes edits to their updates.
                
            Your goal is to take what developers are saying and make edits to an update that you will be provided.
                
            Here are some important rules to follow:
            1. Make edits to the user's standup update. You can make any changes you see fit.
            2. If you notice changes in their preferred writing style, update the preferred style in the provided update. (Something like Paragraph, Bullet points, etc.)
            3. Add or remove any information that you deem necessary given the user's reply.
            4. Valid statuses are NOT_STARTED, IN_PROGRESS, REJECTED, COMPLETED, BLOCKED. Use your best judgment to determine the status.
            5. Return the response in JSON format, following the same structure as the update provided below.

            START EXAMPLE:
            INPUT
            Update: {{\"preferred_style\": \"Paragraph\", \"updates\": [{{\"item\": \"task-1\",\"status\": \"IN_PROGRESS\",\"identified_blockers\": []}}, {{\"item\": \"task-2\",\"status\": \"BLOCKED\",\"identified_blockers\": [\"waiting on team-1\", \"task-4\"]}}]}}
            Human: I actually finished task-1. task-2 is also unblocked now because team-1 has responded. I have also picked up task-3 now. task-4 is on my board but isn't our problem.
                
            OUTPUT
            {{\"preferred_style\": \"Paragraph\", \"updates\": [{{\"item\": \"task-1\",\"status\": \"COMPLETED\",\"identified_blockers\": []}}, {{\"item\": \"task-2\",\"status\": \"IN_PROGRESS\",\"identified_blockers\": []}}, {{\"item\": \"task-3\",\"status\": \"IN_PROGRESS\",\"identified_blockers\": []}}, {{\"item\": \"task-4\",\"status\": \"REJECTED\",\"identified_blockers\": []}}]}}
            
            END EXAMPLE

            Update:
            {update}

            Remember to ensure the response is in JSON format and do not format it with ```json.
            """
        ),
        (
            "human",
            """
            {text}
            """
        )
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    formatted_prompt = prompt.format(update=update, user_id=user_id, text=text)
    response = llm.invoke(formatted_prompt)
    print()
    print("Response is: ", response.content)
    print()
    return json.loads(response.content)

def insufficient_information_response(conversation_history: str) -> str:
    """
    Responds to a user when their standup update is missing information, is vague or unclear, or if you need more details to understand the update.
    """
    formatted_conversation_history = format_conversation_history(conversation_history)
    template = [
        (
            "system",
            """
            You are a project manager whose goal is to read a standup update from a software developer and respond to the message in a professional manner.
            For example, if the user says "Can you update task-1 and task-2", you should respond with "Can you provide more details about the status of task-1 and task-2?"
            
            You may use your own judgment, but please respond to the user asking the information you would need for a sufficient standup update. Keep your response concise and to the point.
            """
        )
    ]
    prompt = ChatPromptTemplate(messages=messages)
    formatted_prompt = prompt.format(formatted_conversation_history=formatted_conversation_history)
    response = llm.invoke(formatted_prompt)
    return response.content

def format_conversation_history(messages: List[Any]) -> str:
    formatted_messages = []
    messages = sorted(messages, key=lambda m: m["ts"])
    for message in messages:
        user = message['user']
        text = message['text']
        formatted_messages.append(f"{user}: {text}")
    return "\n".join(formatted_messages)

def _split_conversation_history(conversation_history: List[str]):
    bot_messages = []
    human_messages = []
    for message in conversation_history:
        if message["user"] == "system":
            bot_messages.append(message["text"])
        else:
            human_messages.append(message["text"])
    return bot_messages, human_messages