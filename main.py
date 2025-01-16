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
from helpers.llm_helpers import extract_updates_from_text
from helpers.slack_helpers import send_standup_messages
from helpers.mongo_db_helpers import get_updates_by_id, insert_item

app = FastAPI()

@app.on_event("startup")
def schedule_jobs():
    # schedule.every().day.at("09:00").do(send_standup_messages)
    schedule.every().minute.do(send_standup_messages)
    
    def run_continuously():
        while True:
            schedule.run_pending()
            time.sleep(1)

    import threading
    threading.Thread(target=run_continuously, daemon=True).start()

load_dotenv(find_dotenv())

@app.post("/verify")
async def verify_slack_events(event: dict):
    def verify_challenge():
        if "challenge" in event:
            return event["challenge"]
        return None
    return {"challenge": verify_challenge()}

@app.post("/slack/events")
async def handle_slack_events(event: dict):
    if "event" in event and event["event"]["type"] == "message":
        user_id = event["event"]["user"]
        text = event["event"]["text"]

        # Extract updates using OpenAI
        extracted_updates = extract_updates_from_text(text)
        print("finished extracting updates")
        pst_timezone = pytz.timezone('America/Los_Angeles')
        now_utc = datetime.now(UTC)
        now_pst = now_utc.astimezone(pst_timezone)

        # Save updates to MongoDB
        insert_item(user_id, extracted_updates, now_pst)

        return {"status": "ok"}

    raise HTTPException(status_code=400, detail="Invalid event format")

@app.get("/updates/{user_id}")
async def get_user_updates(user_id: str):
    return get_updates_by_id(user_id)

# Main entry point to start the FastAPI application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)