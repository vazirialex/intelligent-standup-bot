from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pymongo import MongoClient
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import OpenAI
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests
import schedule
import time
from datetime import datetime, timedelta, UTC
from dotenv import find_dotenv, load_dotenv
import os
import pytz
import helpers.slack_helpers as slack_helpers
from helpers.mongo_db_helpers import get_standup_updates_by_user_id, delete_item
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from agent import agent_executor, execute_agent_with_context
from tool_agent import agent, execute_agent_with_user_context

load_dotenv(find_dotenv())

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

@app.message()
async def respond_to_message(message, say):
    # get standup update if it exists from db then pass it to the agent along with the message text
    # agent_response = agent.invoke(message["text"]).tool_calls
    # agent_response = await execute_agent_with_context(agent_executor, message["text"], message["user"])

    # m = """
    # User id is: {user_id}

    # User message is: {message}
    # # """.format(user_id=message["user"], message=message["text"])
    # # agent_response = execute_agent_with_user_context(m, message["user"]).tool_calls

    # agent_response = agent_executor.invoke(
    #     {
    #         "input": m,
    #         "chat_history": [],
    #     }
    # )

    agent_response = execute_agent_with_user_context(message["text"], message["user"])
    print(agent_response)
    if not agent_response:
        await say(text="Sorry, I didn't understand that.")
        return
    await say(
        # blocks=[
        #     {
        #         "type": "section",
        #         "text": {"type": "mrkdwn", "text": f"Hey there <@{message['user']}>!"},
        #         "accessory": {
        #             "type": "button",
        #             "text": {"type": "plain_text", "text": "Click Me"},
        #             "action_id": "button_click"
        #         }
        #     }
        # ],
        text=f"Hey there <@{message['user']}>. Your response is {agent_response}!"
    )

@app.action("button_click")
async def action_button_click(body, ack, say):
    # Acknowledge the action
    ack()
    await say(f"<@{body['user']['id']}> clicked the button")

@app.command("/get_updates")
async def get_updates(ack, body):
    ack()
    user_id = body["user_id"]
    updates = await get_standup_updates_by_user_id(user_id)
    return updates

@app.command("/delete")
async def delete(ack, body):
    try:
        ack()
        await delete_item(body["user_id"], body["text"])
        return f"Deleted updates for {date}"
    except Exception as e:
        print(e)
        return "Sorry, we weren't able to delete the updates."

async def schedule_standup_message():
    num_seconds_in_one_day = 86400
    while True:
        await slack_helpers.send_standup_messages()
        await asyncio.sleep(num_seconds_in_one_day)

async def main():
    asyncio.ensure_future(schedule_standup_message())
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    await handler.start_async()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())