from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import requests
from dotenv import find_dotenv, load_dotenv
import os
import json

load_dotenv(find_dotenv())
# llm = ChatOpenAI(
#     model="gpt-4o-mini",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
#     api_key=os.environ["OPENAI_API_KEY"]
# )

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20240620",
    temperature=0,
    max_tokens=1024,
    timeout=None,
    max_retries=2
)

def extract_updates_from_text(text: str):
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
            "{text}"
        )
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    formatted_prompt = prompt.format(text=text)
    response = llm.invoke(formatted_prompt)
    return json.loads(response.content)

def insufficient_information_response(conversation_history):
    """
        EDIT: TURN EACH ELEMENT IN THE CONVERSATION HISTORY INTO A MESSAGE SEPARATED BY BOT AND HUMAN
    """
    template = """
    You are a project manager whose goal is to read a standup update from a software developer and classify it as an update to an existing ticket given conversation history.
    Given {conversation_history}, please respond to the user asking the information you would need for a sufficient standup update.
    
    """
    prompt = ChatPromptTemplate(messages=messages)
    formatted_prompt = prompt.format(conversation_history=conversation_history)
    response = llm.invoke(formatted_prompt)
    return json.loads(response.content)

def classify_message(text):
    template = """
    You are a project manager whose goal is to read a standup update from a software developer and classify it as an update to an existing ticket given conversation history.
    
    """
    prompt = ChatPromptTemplate(
        input_variables=["text"],
        template="Extract ticket updates from the following standup update text: {text}. Provide the ticket number and status update."
    )
    formatted_prompt = prompt.format(text=text)
    response = openai.run(formatted_prompt)
    return response