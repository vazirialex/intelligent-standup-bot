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
from .github_helpers import fetch_github_activity

load_dotenv(find_dotenv())

slack_client = WebClient(token=os.environ["SLACK_API_TEST_OAUTH_TOKEN"])
_usergroup_id = os.environ["SLACK_USER_GROUP_ID"]

def get_all_users():
    try:
        response = slack_client.usergroups_users_list(usergroup=_usergroup_id)
        users = response["users"]
        return users
    except SlackApiError as e:
        print(f"Error fetching users: {e.response['error']}")
        raise e

def send_standup_messages():
    users = get_all_users()
    for user_id in users:
        print(f"Sending standup message to {user_id}")
        try:
            # Fetch GitHub activity
            # github_activity = fetch_github_activity(user_id)
            github_activity = [
                {"type": "PushEvent", "repo": "repo1", "created_at": "2022-01-01T00:00:00Z", "commit": "123"}, 
                {"type": "PullRequestEvent", "repo": "repo2", "created_at": "2022-01-01T00:00:00Z", "pull_request": "456"}
            ]
            slack_client.chat_postMessage(
                channel=user_id,
                text=f"Good morning! Here's your GitHub activity from the past 24 hours: {github_activity}. Please reply with your standup update."
            )
        except SlackApiError as e:
            print(f"Error sending message to {user_id}: {e.response['error']}")