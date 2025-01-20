from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timedelta
from dotenv import find_dotenv, load_dotenv
import os
from .mongo_db_helpers import persist_scheduled_message, standup_message_sent, insert_item
from .llm_helpers import derive_standup_message, create_standup_update
from .github_helpers import get_github_token, generate_github_oauth_url

load_dotenv(find_dotenv())

slack_client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
_usergroup_id = os.environ["SLACK_USER_GROUP_ID"]

def _get_all_users():
    try:
        response = slack_client.usergroups_users_list(usergroup=_usergroup_id)
        users = response["users"]
        return users
    except SlackApiError as e:
        print(f"Error fetching users: {e.response['error']}")
        raise e

def fetch_conversation_history(channel_id, date=None, max_number_of_messages_to_fetch=10):
    try:
        response = slack_client.conversations_history(channel=channel_id)
        messages = response["messages"]
        target_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_timestamp = target_date.timestamp()
        return [msg for msg in messages if float(msg["ts"]) >= start_timestamp][:max_number_of_messages_to_fetch]
    except SlackApiError as e:
        print(f"Error fetching conversation history: {e.response['error']}")
        return []

async def send_standup_messages():
    users = _get_all_users()
    now = datetime.now()
    for user_id in users:
        try:
            standup_message = None
            github_token = get_github_token(user_id)
            if not github_token:
                oauth_url = generate_github_oauth_url(user_id, user_id)
                response = {
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": "Good morning! :wave: Time for your standup update!"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "It looks like you haven't connected your GitHub account to the standup bot yet. Please connect your GitHub account to the standup bot so that I can help you with your standup updates. You can do this by clicking the button below."
                            }
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Connect GitHub"
                                    },
                                    "url": oauth_url,
                                    "style": "primary"
                                }
                            ]
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "In the meantime, please provide your standup update including your statuses, plans for today, and any blockers you're facing. Thank you!"
                            }
                        }
                    ],
                    "response_type": "ephemeral"
                }
                standup_message = "Hello! Please provide your standup update including your statuses, plans for today, and any blockers you're facing. Thank you!"
                slack_client.chat_postMessage(
                    channel=user_id,
                    blocks=response["blocks"],
                    text=standup_message
                )
            else:
                standup_message = derive_standup_message(user_id)
                # slack_client.chat_scheduleMessage(
                #     channel=user_id,
                #     text=standup_message,
                #     post_at=int(datetime.combine(now.date(), datetime.min.time()).timestamp()) + 9 * 60 * 60 # 9 am current day
                # )

                # TODO: Remove this after testing
                slack_client.chat_postMessage(
                    channel=user_id,
                    text=standup_message
                )
            persist_scheduled_message(user_id, standup_message, now)
        except SlackApiError as e:
            print(f"Error sending message to {user_id}: {e.response['error']}")

def send_github_oauth_message(channel_id, user_id):
    # slack_client.chat_postMessage(
    #     channel=channel_id,
    #     user=user_id,
    #     text="Successfully connected your GitHub account! :white_check_mark:"
    # )
    slack_client.chat_postMessage(
        channel=user_id,
        user=user_id,
        text="Successfully connected your GitHub account! :white_check_mark:"
    )
