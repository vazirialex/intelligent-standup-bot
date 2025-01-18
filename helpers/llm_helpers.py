from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.messages.system import SystemMessage
from dotenv import find_dotenv, load_dotenv
import os
import json
from typing import List, Any
from .mongo_db_helpers import get_standup_updates_by_user_id, get_messages_from_db

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
    Only use this tool if there is no update already in the database.
    """
    messages = [
        SystemMessage(
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
        HumanMessage(content=
            f"""
            My user id is {user_id}

            My response is {text}
            """
        )
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    formatted_prompt = prompt.format(user_id=user_id, text=text)
    response = llm.invoke(formatted_prompt)
    return json.loads(response.content)

def make_edits_to_update(update_exists: bool, text: str, user_id: str, channel_id: str) -> dict:
    """
    Given an update and a user's reply, make edits to the user's standup update based on the conversation history and the user's reply. Only make edits if there is sufficient information to make edits.
    """
    update = get_standup_updates_by_user_id(user_id) if update_exists else False
    if not update:
        print("make edits to update called but no update exists")
        return ask_question_response(user_id, channel_id, text)
    chat_history = get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=4)
    formatted_chat_history = convert_conversation_history_to_langchain_messages(chat_history)
    messages = [
        SystemMessage(
            """
            You are a project manager that listens to standup updates from developers and makes edits to their updates.
                
            Your goal is to take what developers are saying and make edits to an update that you will be provided.
                
            Here are some important rules to follow:
            1. Make edits to the user's standup update. You can make any changes you see fit.
            2. If you notice changes in their preferred writing style, update the preferred style in the provided update. (Something like Paragraph, Bullet points, etc.)
            3. Add or remove any information that you deem necessary given the user's reply.
            4. Valid statuses are NOT_STARTED, IN_PROGRESS, REJECTED, COMPLETED, BLOCKED. Use your best judgment to determine the status.
            5. Return the response in JSON format, following the same structure as the update provided below.
            6. Do not make up any information or tasks. Only make edits to the information provided.

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
        *formatted_chat_history,
        HumanMessage(content=text)
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    formatted_prompt = prompt.format(update=update, user_id=user_id, text=text)
    response = llm.invoke(formatted_prompt)
    print()
    print("Response from llm for update edits: ", response.content)
    print()
    return json.loads(response.content)

def ask_question_response(user_id: str, channel_id: str, message: str) -> str:
    """
    Responds to the user with appropriate clarifying questions when their standup update is missing information, is vague or unclear, or if more details are needed to understand the update.
    """
    # conversation_history = fetch_conversation_history(channel_id, max_number_of_messages_to_fetch=6)
    conversation_history = get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=6)
    formatted_conversation_history = convert_conversation_history_to_langchain_messages(conversation_history)
    messages = [
        SystemMessage(
            """
            You are a project manager whose goal is to read a standup update from a software developer and respond to the message in a professional manner.
            For example, if the user says "Can you update task-1 and task-2", you should respond with "Can you provide more details about the status of task-1 and task-2?"

            You will be provided a conversation history of the user, their most recent message, and their standup update conversation thus far. 
            You should respond to the user asking the information you would need for a sufficient standup update.

            Here is what constitutes a sufficient standup update:
            - The user has provided a list of tasks and their statuses. Use the conversation history to determine if the user has provided a list of tasks and their statuses.
            - If a user has a blocked task, you should ask them why it's blocked to keep track of identified blockers per task

            Only ask what you need to get the tasks, statuses, and potential blockers.

            You may use your own judgment to help you determine if the user has provided a sufficient standup update. Keep your response concise and to the point.
            """
        ),
        *formatted_conversation_history,
        HumanMessage(content=message)
    ]
    response = llm.invoke(messages)
    return response.content

def friendly_conversation_response(user_id: str, channel_id: str, message: str) -> str:
    """
    Responds to generic messages from the user that are not standup updates, such as common replies that end a conversation.
    """
    # conversation_history = fetch_conversation_history(channel_id, max_number_of_messages_to_fetch=6)
    conversation_history = get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=2)
    formatted_conversation_history = convert_conversation_history_to_langchain_messages(conversation_history)
    messages = [
        SystemMessage(
            """
            You are a project manager whose goal is to read a standup update from a software developer and respond to the message in a professional manner.
            For example, if the user says "Can you update task-1 and task-2", you should respond with "Can you provide more details about the status of task-1 and task-2?"

            You will be provided a conversation history of the user, their most recent message, and their standup update conversation thus far. 
            You should respond to the user asking the information you would need for a sufficient standup update.

            You may use your own judgment, but please respond to the user asking the information you would need for a sufficient standup update. Keep your response concise and to the point.
            """
        ),
        *formatted_conversation_history,
        HumanMessage(content=message)
    ]
    response = llm.invoke(messages)
    return response.content

def convert_slack_history_to_langchain_messages(slack_conversation_history):
    messages = []
    for message in slack_conversation_history:
        if message.get('bot_id'):
            messages.append(AIMessage(content=message['text']))
        else:
            messages.append(HumanMessage(content=message['text']))
    return messages

def convert_conversation_history_to_langchain_messages(conversation_history):
    messages = []
    for message in conversation_history:
        if message.get('is_bot'):
            messages.append(AIMessage(content=message['message']))
        else:
            messages.append(HumanMessage(content=message['message']))
    return messages

def _split_conversation_history(conversation_history: List[str]):
    bot_messages = []
    human_messages = []
    for message in conversation_history:
        if message["user"] == "system":
            bot_messages.append(message["text"])
        else:
            human_messages.append(message["text"])
    return bot_messages, human_messages