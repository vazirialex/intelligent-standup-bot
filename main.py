from dotenv import find_dotenv, load_dotenv
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import helpers.slack_helpers as slack_helpers
from helpers.mongo_db_helpers import get_standup_updates_by_user_id, delete_item, save_message_to_db, delete_github_token
from helpers.github_helpers import generate_github_oauth_url, get_github_activity
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from tool_agent import execute_agent_with_user_context
from reply_agent import reply
from github_oauth_connection import GitHubCallbackHandler

load_dotenv(find_dotenv())

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

@app.message()
async def respond_to_message(message, say):
    save_message_to_db(message["user"], message["text"], message["channel"], False)
    tool_agent_response, used_tool = execute_agent_with_user_context(message["text"], message["user"], message["channel"])
    if not tool_agent_response:
        await say(text="Sorry, I didn't understand that.")
        return
    reply_agent_response = reply(tool_agent_response, message["channel"], message["user"], message["text"], used_tool)
    save_message_to_db(message["user"], reply_agent_response, message["channel"], True)
    await say(text=reply_agent_response)

@app.command("/get_updates")
async def get_updates(ack, body):
    ack()
    user_id = body["user_id"]
    updates = await get_standup_updates_by_user_id(user_id)
    return updates

@app.command("/delete-standup-update")
async def delete_standup_update(ack, body):
    try:
        ack()
        await delete_item(body["user_id"], body["text"])
        return f"Deleted updates for {body['user_id']}"
    except Exception as e:
        print(e)
        return "Sorry, we weren't able to delete the updates."

@app.command("/connect-github")
async def connect_github(ack, body, say):
    """Slack command to initiate GitHub connection."""
    await ack()
    
    # Use Slack user ID as state parameter
    state = body["user_id"]
    channel_id = body["channel_id"]
    oauth_url = generate_github_oauth_url(state, channel_id)
    
    # Send ephemeral message with OAuth link
    await say({
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Click the button below to connect your GitHub account:"
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
            }
        ],
        "response_type": "ephemeral"
    })

@app.command("/standup")
async def handle_standup_command(ack, respond, command):
    await ack()
    slack_user_id = command['user_id']
    
    # Get GitHub activity
    github_data = get_github_activity(slack_user_id)
    
    if isinstance(github_data, str):
        # User needs to connect GitHub
        await respond(github_data)
        return
    
    # Format activity for standup context
    activity_summary = "Here's your GitHub activity from the past 24 hours:\n"
    if github_data['commits']:
        activity_summary += "\nCommits:\n" + "\n".join([
            f"- [{c['repo']}] {c['message']}" for c in github_data['commits']
        ])
    if github_data['pull_requests']:
        activity_summary += "\nPull Requests:\n" + "\n".join([
            f"- [{pr['repo']}] {pr['title']} ({pr['state']})" for pr in github_data['pull_requests']
        ])
    
    activity_summary += "\n\nPlease reply with your standup update."
    
    await respond(activity_summary)

@app.command("/github-logout")
async def github_logout(ack, body, say):
    await ack()
    #delete the github token from the database
    delete_github_token(body["user_id"])
    await say("Logged out of GitHub")

async def schedule_standup_message():
    num_seconds_in_one_day = 86400 - 5 * 60 # 5 minutes before 9 am
    while True:
        await slack_helpers.send_standup_messages()
        await asyncio.sleep(num_seconds_in_one_day)

async def main():
    asyncio.ensure_future(schedule_standup_message())
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    await handler.start_async()

def run_http_server():
    """Run the HTTP server for GitHub callbacks."""
    server = HTTPServer(('localhost', 3000), GitHubCallbackHandler)
    server.serve_forever()

if __name__ == "__main__":
    import asyncio
    import threading
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    asyncio.run(main())