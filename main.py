from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pymongo import MongoClient
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import OpenAI
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import time
from datetime import datetime, timedelta
from dotenv import find_dotenv, load_dotenv
import os
import pytz

@asynccontextmanager
async def trigger_standup_notification(app: FastAPI):
    scheduler = AsyncIOScheduler(timezone="US/Pacific")
    trigger = CronTrigger(year="*", month="*", day="*", hour="9", minute="0", second="0")
    scheduler.add_job(func=send_standup_messages, trigger=trigger)
    scheduler.start()
    yield

app = FastAPI(lifespan=trigger_standup_notification)

load_dotenv(find_dotenv())

# MongoDB Configuration
client = MongoClient("mongodb://localhost:27017/")
db = client["standup_db"]
updates_collection = db["daily_updates"]

# Slack Configuration
slack_client = WebClient(token=os.environ["SLACK_API_TEST_OAUTH_TOKEN"])
users = ["U123456", "U654321"]  # Replace with actual Slack user IDs

# GitHub Configuration
github_api_base_url = "https://api.github.com"
github_token = os.environ["GITHUB_TOKEN"]
github_headers = {
    "Authorization": f"Bearer {github_token}",
    "Accept": "application/vnd.github+json",
}
# OpenAI Configuration
openai = OpenAI(temperature=0., api_key=os.environ["OPEN_AI_API_KEY"])

def send_standup_messages():
    template = """
    
    """
    for user_id in users:
        try:
            # Fetch GitHub activity
            github_activity = fetch_github_activity(user_id)
            slack_client.chat_postMessage(
                channel=user_id,
                text=f"Good morning! Here's your GitHub activity from the past 24 hours: {github_activity}. Please reply with your standup update."
            )
        except SlackApiError as e:
            print(f"Error sending message to {user_id}: {e.response['error']}")

def fetch_github_activity(user_id):
    # Map Slack user IDs to GitHub usernames (custom mapping needed)
    github_username = user_id_to_github_username(user_id)
    since = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    print(f"Fetching GitHub activity for {github_username} since {since}")
    response = requests.get(
        f"{github_api_base_url}/users/{github_username}/events",
        headers=github_headers,
        params={"since": since},
    )
    if response.status_code == 200:
        return response.json()
    else:
        return "No activity or unable to fetch."

def user_id_to_github_username(user_id):
    # Placeholder for actual mapping logic
    mapping = {"U123456": "github_user1", "U654321": "github_user2"}
    return mapping.get(user_id, "unknown")

@app.post("/verify")
async def verify_slack_events(event: dict):
    def verify_challenge():
        if "challenge" in event:
            return event["challenge"]
        return None
    return {"challenge": verify_challenge()}

@app.post("/slack/events")
async def handle_slack_events(event: dict):
    def verify_challenge():
        if "challenge" in event:
            return event["challenge"]
        return None
    challenge = verify_challenge()
    if "event" in event and event["event"]["type"] == "message":
        user_id = event["event"]["user"]
        text = event["event"]["text"]

        # Extract updates using OpenAI
        extracted_updates = extract_updates_from_text(text)
        pst_timezone = pytz.timezone('America/Los_Angeles')
        now_pst = now_utc.astimezone(pst_timezone)

        # Save updates to MongoDB
        updates_collection.insert_one({
            "user_id": user_id,
            "updates": extracted_updates,
            "timestamp": now_pst # change to pst
        })

        return {"status": "ok", "challenge": challenge}

    raise HTTPException(status_code=400, detail="Invalid event format")

def extract_updates_from_text(text):
    template = """
    You are a project manager that listens to standup updates from developers and extracts their key insights.
        
    Your goal is to take what developers are saying and extract all updates.
        
    Here are some important rules to follow:
    1. 
    2. 
    3. 
    
    """
    prompt = ChatPromptTemplate(
        input_variables=["text"],
        template="Extract ticket updates from the following standup update text: {text}. Provide the ticket number and status update."
    )
    formatted_prompt = prompt.format(text=text)
    response = openai.run(formatted_prompt)
    return response

@app.get("/updates/{user_id}")
async def get_user_updates(user_id: str):
    updates = list(updates_collection.find({"user_id": user_id}, {"_id": 0}))
    if updates:
        return updates
    raise HTTPException(status_code=404, detail="No updates found for user")

# Main entry point to start the FastAPI application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)