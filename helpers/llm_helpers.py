from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.messages.system import SystemMessage
from dotenv import find_dotenv, load_dotenv
import os
import json
from datetime import datetime, timedelta
from .mongo_db_helpers import get_standup_updates_by_user_id, get_messages_from_db, update_exists
from .github_helpers import get_github_activity, get_github_token
from .format_helpers import format_github_activity_to_slack, format_standup_update_to_slack

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

def create_standup_update(text: str, user_id: str, channel_id: str) -> dict:
    """
    Given a user's standup update and conversation history, extract the key insights from the update if and only ifthe update has sufficient information.
    Uses the conversation history if needed to piece together the user's standup update.
    Only use this tool if there is no update already in the database and if there is sufficient information to update, delete, or add a given item.
    """
    prompt_with_day_differentiation = """
        You are a project manager that listens to standup updates from developers and extracts their key insights.
            
        Your goal is to take what developers are saying about their tasks and extract all updates. You will be given a conversation history between you and the user.
            
        Here are some important rules to follow:
        1. You may be given github activity and linear activity within your conversation history. Use either the PR number, ticket number, or linear ticket number to define the item field.
        2. You can use the linear ticket status or github PR status to define the status field. The status should be one of NOT_STARTED, IN_PROGRESS, REJECTED, COMPLETED, IN_REVIEW, OR BLOCKED. Use your best judgment to determine.
        3. Identify the user's writing style and tone and summarize it in one word (e.g. Paragraph, Bullet points, etc.)
        4. If the user's update applies to the previous day, add it to the "yesterday" field. If the user's update applies to the current day, add it to the "today" field.
        5. If no update exists for either today or yesterday, add set that corresponding "today" or "yesterday" field to an empty array.
        6. You are given conversation history between you and the user. Use this conversation history to determine if the user has provided sufficient information to craft a response.
        7. Return your response in JSON with the following structure: {{\"preferred_style\": \"Paragraph\", \"updates\": {\"yesterday\": [{{\"item\": \"task-1\", \"status\": \"IN_PROGRESS\", \"identified_blockers\": []}}, {{\"item\": \"task-2\", \"status\": \"BLOCKED\", \"identified_blockers\": [\"waiting on team-1\", \"task-4\"]}}], \"today\": [{{\"item\": \"task-3\", \"status\": \"IN_PROGRESS\", \"identified_blockers\": []}}, {{\"item\": \"task-4\", \"status\": \"REJECTED\", \"identified_blockers\": []}}]}}}
        8. Only use valid JSON. Do not format it with ```json.

        Example:
        INPUT
        - I raised a PR for task-1. I am working on raising a PR for fixing the counter button bug. 
        - I pushed the fix for task-3 to production so we can close that out.
        - Task-4 is currently blocked while we wait for task-5 to be completed

        OUTPUT
        {{\"preferred_style\": \"Bullet points\", \"updates\": {{\"yesterday\": [{{\"item\": \"task-1\", \"status\": \"IN_REVIEW\", \"identified_blockers\": []}}, {{\"item\": \"task-3\", \"status\": \"COMPLETED\", \"identified_blockers\": []}}], \"today\": [{{\"item\": \"counter button bug\", \"status\": \"IN_PROGRRESS\", \"identified_blockers\": []}}, {{\"item\": \"task-4\", \"status\": \"BLOCKED\", \"identified_blockers\": [\"task-5\"]}}]}}}}
        """

    prompt_without_day_differentiation = """
            You are a project manager that listens to standup updates from developers and extracts their key insights.
                
            Your goal is to take what developers are saying and extract all updates.
                
            Here are some important rules to follow:
            1. Identify the ticket number and status update. The status should be one of NOT_STARTED, IN_PROGRESS, IN_REVIEW, REJECTED, COMPLETED, OR BLOCKED. Use your best judgment to determine the status.
            2. Identify the user's writing style and tone and summarize it in one word (e.g. Paragraph, Bullet points, etc.)
            3. You are given conversation history between you and the user. Use this conversation history to determine if the user has provided sufficient information to craft a response.
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
    messages = [
        # TODO: add conversation history if the user does not have an update in the database
        # TODO: Update this to only give the standup update scheduled message and the user's reply after that?
        *convert_conversation_history_to_langchain_messages(
            get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=2)
        ),
        SystemMessage(prompt_without_day_differentiation),
        HumanMessage(content=text)
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    formatted_prompt = prompt.format(user_id=user_id, text=text)
    response = llm.invoke(formatted_prompt)
    print("response from create standup update: ", response)
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
    prompt_with_day_differentiation = """
        You are a project manager that listens to standup updates from developers and makes edits to their updates.
            
        Your goal is to take what developers are saying and make edits to an update that you will be provided.
            
        Here are some important rules to follow:
        1. Make edits to the user's standup update. You can make any changes you see fit.
        2. Analyze whether the user's update applies to the previous day or is an update for the current day. You can use the conversation context and even their grammar to determine this.
        3. If you notice changes in their preferred writing style, update the preferred style in the provided update. (Something like Paragraph, Bullet points, etc.)
        4. Valid statuses are NOT_STARTED, IN_PROGRESS, REJECTED, IN_REVIEW, COMPLETED, BLOCKED. Use your best judgment to determine the status.
        5. Return the response in JSON format, following the same structure as the update provided below.
        6. Do not make up any information or tasks. Only make edits to the information provided.
        7. Only update tasks that need updating. Do not edit any other tasks that the user has not mentioned.

        START EXAMPLE:
        INPUT
        Update: {{\"preferred_style\": \"Paragraph\", \"updates\": {{\"yesterday\": [{{\"item\": \"task-1\", \"status\": \"IN_PROGRESS\", \"identified_blockers\": []}}, {{\"item\": \"task-2\", \"status\": \"BLOCKED\", \"identified_blockers\": [\"waiting on team-1\", \"task-4\"]}}], \"today\": []}}}}
        Human: I actually finished task-1. task-2 is also unblocked now because team-1 has responded. I have also picked up task-3 now. task-4 is on my board but isn't our problem.
            
        OUTPUT
        {{\"preferred_style\": \"Paragraph\", \"updates\": {{\"yesterday\": [{{\"item\": \"task-1\", \"status\": \"COMPLETED\", \"identified_blockers\": []}}, {{\"item\": \"task-2\", \"status\": \"IN_PROGRESS\", \"identified_blockers\": []}}], \"today\": [{{\"item\": \"task-3\", \"status\": \"IN_PROGRESS\", \"identified_blockers\": []}}, {{\"item\": \"task-4\", \"status\": \"REJECTED\", \"identified_blockers\": []}}]}}}}

        END EXAMPLE

        Update: 
        {update}

        Remember to ensure the response is in JSON format and do not format it with ```json.
        """

    prompt_without_day_differentiation = """
        You are a project manager that listens to standup updates from developers and makes edits to their updates.
            
        Your goal is to take what developers are saying and make edits to an update that you will be provided.
            
        Here are some important rules to follow:
        1. Identify tasks that need updating or add new tasks if they are not already in the update.
        2. If you notice changes in their preferred writing style, update the preferred style in the provided update. (Something like Paragraph, Bullet points, etc.)
        3. Add or remove any information that you deem necessary given the user's reply.
        4. Valid statuses are NOT_STARTED, IN_PROGRESS, IN_REVIEW, REJECTED, COMPLETED, and BLOCKED. Use your best judgment to determine the status.
        5. Return the response in JSON format, following the same structure as the update provided below.
        6. Do not make up any information or tasks. Only make edits to the information provided.

        START EXAMPLE:
        INPUT
        Update: {{\"preferred_style\": \"Paragraph\", \"updates\": [{{\"item\": \"task-1\",\"status\": \"IN_PROGRESS\",\"identified_blockers\": []}}, {{\"item\": \"task-2\",\"status\": \"BLOCKED\",\"identified_blockers\": [\"waiting on team-1\", \"task-4\"]}}]}}
        Human: I actually finished task-1. task-2 is also unblocked now because team-1 has responded. I have also picked up task-3 now. task-4 is on my board but isn't our problem.
            
        OUTPUT
        {{\"preferred_style\": \"Paragraph\", \"updates\": [{{\"item\": \"task-1\",\"status\": \"COMPLETED\",\"identified_blockers\": []}}, {{\"item\": \"task-2\",\"status\": \"IN_PROGRESS\",\"identified_blockers\": []}}, {{\"item\": \"task-3\",\"status\": \"IN_PROGRESS\",\"identified_blockers\": []}}, {{\"item\": \"task-4\",\"status\": \"REJECTED\",\"identified_blockers\": []}}]}}
        
        END EXAMPLE

        Here is the current standup update that you will be editing as needed:
        {update}

        Remember to ensure the response is in JSON format and do not format it with ```json.
        """
    messages = [
        *formatted_chat_history,
        SystemMessage(
            prompt_without_day_differentiation
        ),
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
    # """
    # Responds to the user with appropriate clarifying questions when their standup update is missing information, is vague or unclear, or if more details are needed to understand the update.
    # Use this tool when there is missing updates about about the current day or if the user is starting a conversation and no standup update exists.
    # """
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
            - The user has either approved the standup update auto-generated by a scheduled message or they have provided a list of tasks and their statuses for BOTH the previous and current day.

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
    Responds to generic messages from the user that are not standup updates only if the user has provided a standup update, such as common replies that end a conversation.
    """
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
    """
    DO NOT USE THIS FUNCTION.
    """
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

def derive_standup_message(user_id: str) -> str:
    """
    Uses github and linear to generate a well-formatted standup message for a user.
    """
    github_activity = get_github_activity(user_id) if get_github_token(user_id) else "No github activity"
    formatted_github_activity = format_github_activity_to_slack(github_activity)
    yesterday = datetime.now() - timedelta(days=1)
    previous_standup_update = get_standup_updates_by_user_id(user_id, yesterday.strftime("%Y-%m-%d"))[0] if update_exists(user_id, yesterday.strftime("%Y-%m-%d")) else "No updates provided"

    print("previous standup update: ", previous_standup_update)
    print()
    print()

    messages = [
        SystemMessage(
            """
            You are a project manager whose job is to create a well-formatted standup message in slack for a software developer given their github activity and previous standup updates.

            Here are some important things to keep in mind when crafting the standup message:
            1. The message should be well-formatted and easy to read. You are sending a message in slack, so use emojis and formatting to make the message more readable, but DO NOT use markdown.
            2. Your message is FOR a developer, so your goal should be to help make their standup update easier by finding what they did for them.
            3. Find trends in the github activity and ask if anything needs to be escalated. For example, if a PR is left open, ask if the developer needs help getting it reviewed and merged.
            4. You should only be using the github activity and previous standup updates to correlate the standup update to the github activity. See if you can make inferences on the new status of the tasks based on the github activity and update.
            5. Since you are only going to be given previous data, try to make inferences on what the user is going to do for the current day based on the github activity and previous standup update.
            6. If there are no inferences you can make on their current day plans, ask them what they plan on doing for the current day.
            7. Also ask them to confirm if the update looks good to them.


            {formatted_github_activity}

            {formatted_previous_standup_update}

            """.format(formatted_github_activity=format_github_activity_to_slack(github_activity), formatted_previous_standup_update=formatted_github_activity)
        )
    ]
    response = llm.invoke(messages)
    return response.content

def create_standup_update_from_conversation_history(text: str, user_id: str, channel_id: str) -> dict:
    """
    Creates a standup update from a conversation history with the user in cases where the user accepts the standup update provided by the scheduled message.
    """
    messages = [
        SystemMessage(
            """
            You are a project manager that listens to standup updates from developers and extracts their key insights.
                
            Your goal is to take what developers are saying about their tasks and extract all updates. You will be given a previous standup update and what the user has said in the conversation history.
            Using this information, you must determine if you should create the standup update or reply to the user asking for help.
                
            Here are some important rules to follow:
            1. First, determine if the user has accepted the standup update provided by the scheduled message. If they have, create the standup update.
            2. You can use the linear ticket status or github PR status to define the status field. The status should be one of NOT_STARTED, IN_PROGRESS, REJECTED, COMPLETED, IN_REVIEW, OR BLOCKED. Use your best judgment to determine.
            3. Identify the user's writing style and tone and summarize it in one word (e.g. Paragraph, Bullet points, etc.)
            4. You are given conversation history between you and the user. Use this conversation history to determine if the user has provided sufficient information to craft a response.
            5. Return your response in JSON format with the following structure: {{\"preferred_style\": \"Paragraph\", \"updates\": [{{\"item\": \"task-1\",\"status\": \"IN_PROGRESS\",\"identified_blockers\": []}}, {{\"item\": \"PR#123\",\"status\": \"BLOCKED\",\"identified_blockers\": [\"waiting on team-1\", \"task-4\"]}}]}}

            Example:
            INPUT
            - I raised a PR for task-1. I am working on raising a PR for fixing the counter button bug. 
            - I pushed the fix for task-3 to production so we can close that out.
            - Task-4 is currently blocked while we wait for task-5 to be completed

            OUTPUT
            {{
                \"preferred_style\": \"Bullet points\",
                \"updates\": [
                    {{
                        \"item\": \"task-1\",
                        \"status\": \"IN_REVIEW\",
                        \"identified_blockers\": []
                    }},
                    {{
                        \"item\": \"counter button bug\",
                        \"status\": \"IN_PROGRRESS\",
                        \"identified_blockers\": []
                    }},
                    {{
                        \"item\": \"task-3\",
                        \"status\": \"COMPLETED\",
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
        # TODO: add conversation history if the user does not have an update in the database
        # TODO: Update this to only give the standup update scheduled message and the user's reply after that?
        *convert_conversation_history_to_langchain_messages(
            get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=6)
        ),
        HumanMessage(content=
            f"""
            {text}
            """
        )
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    formatted_prompt = prompt.format(user_id=user_id, text=text)
    response = llm.invoke(formatted_prompt)
    return json.loads(response.content)