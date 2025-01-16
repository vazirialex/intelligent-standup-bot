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
from datetime import datetime, timedelta, UTC
from dotenv import find_dotenv, load_dotenv
import os
import pytz

load_dotenv(find_dotenv())

github_api_base_url = "https://api.github.com"
github_token = os.environ["GITHUB_TOKEN"]
github_headers = {
    "Authorization": f"Bearer {github_token}",
    "Accept": "application/vnd.github+json",
}

def _slack_user_id_to_github_username(user_id):
    # Placeholder for actual mapping logic
    mapping = {"U123456": "github_user1", "U654321": "github_user2"}
    return mapping.get(user_id, "unknown")

def fetch_github_activity(user_id):
    # Map Slack user IDs to GitHub usernames (custom mapping needed)
    github_username = _slack_user_id_to_github_username(user_id)
    pst_timezone = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(UTC)
    now_pst = now_utc.astimezone(pst_timezone)
    since = (now_pst - timedelta(days=1)).isoformat() + "Z"
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