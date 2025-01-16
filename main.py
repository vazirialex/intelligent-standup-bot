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
from helpers.mongo_db_helpers import get_updates_by_id, insert_item
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

load_dotenv(find_dotenv())

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

@app.message()
async def respond_to_message(message, say):
    # say() sends a message to the channel where the event was triggered
    print(message)
    extracted_updates = slack_helpers.handle_new_message(message)
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
        text=f"Hey there <@{message['user']}>. Your response is {extracted_updates}!"
    )

@app.action("button_click")
async def action_button_click(body, ack, say):
    # Acknowledge the action
    ack()
    await say(f"<@{body['user']['id']}> clicked the button")

async def schedule_standup_message():
    while True:
        await slack_helpers.send_standup_messages()
        await asyncio.sleep(180)

async def main():
    asyncio.ensure_future(schedule_standup_message())
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    await handler.start_async()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())