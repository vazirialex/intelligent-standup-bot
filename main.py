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
from helpers.mongo_db_helpers import get_updates_by_id, delete_item
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from agent import agent

load_dotenv(find_dotenv())

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

@app.message()
async def respond_to_message(message, say):
    # say() sends a message to the channel where the event was triggered
    agent_response = agent.invoke(message["text"]).tool_calls
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
    updates = await get_updates_by_id(user_id)
    return updates

@app.command("/delete")
async def delete(ack, body):
    try:
        ack()
        await delete_item(body["user_id"], body["text"])
        return f"Deleted updates for {date}"
    except Exception as e:
        print(e)
        return f"Sorry, we weren't able to delete the updates."

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