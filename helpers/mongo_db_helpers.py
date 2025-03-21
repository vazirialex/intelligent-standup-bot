from pymongo import MongoClient
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client["standup_db"]
updates_collection = db["daily_updates"]
messages_collection = db["messages"]
github_tokens_collection = db["github_tokens"]

def get_standup_updates_by_user_id(user_id: str, date = None):
    """
    Get standup updates for a user since the given date
    """
    today = datetime.now().strftime("%Y-%m-%d")
    query_date = date if date else today
    db_query = {
        "user_id": user_id,
        "date": {"$gte": query_date}  # Get all updates with date greater than or equal to query_date
    }
    updates = list(updates_collection.find(db_query, {"_id": 0}))

    if updates:
        return updates  # Return all updates, not just the first one
    raise Exception(f"No updates found for user {user_id} on date {query_date}")

def insert_item(user_id, extracted_updates):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    if update_exists(user_id):
        update_item(user_id, extracted_updates)
    else:
        updates_collection.insert_one({
            "user_id": user_id,
            "updates": extracted_updates,
            "date": date,
            "update_time": now
        })

def update_exists(user_id, date = None) -> bool:
    """
    Check if an update exists in our DB for a user on a given date
    """
    desired_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d")
    return updates_collection.find_one({"user_id": user_id, "date": desired_date}) is not None

def update_item(user_id, extracted_updates):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    updates_collection.update_one(
        {"user_id": user_id, "date": date},
        {"$set": {"updates": extracted_updates, "update_time": now}}
    )

def delete_item(user_id, date = None):
    desired_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d")
    updates_collection.delete_one({"user_id": user_id, "date": desired_date})

def persist_scheduled_message(user_id, message, scheduled_time):
    messages_collection.insert_one({
        "type": "scheduled_message",
        "is_bot": True,
        "user_id": user_id,
        "channel_id": user_id,
        "message": message,
        "timestamp": scheduled_time
    })

def standup_message_sent(user_id, date = None):
    return messages_collection.find_one({"user_id": user_id, "type": "scheduled_message", "date": date}) is not None

def save_message_to_db(user_id, message, channel_id, is_bot):
    messages_collection.insert_one({
        "type": "message",
        "is_bot": is_bot,
        "user_id": user_id,
        "message": message,
        "channel_id": channel_id,
        "timestamp": datetime.now()
    })

def get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=10, date=None):
    desired_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d") # if date is not provided, get messages from today
    result = list(
        messages_collection.find(
            {
                "user_id": user_id, 
                "channel_id": channel_id, 
                "timestamp": {"$gte": desired_date}
            }, 
            {
                "_id": 0
            }
        )
        .sort("timestamp", -1))
    return result[:max_number_of_messages_to_fetch]

def save_github_token(slack_user_id: str, github_token: str):
    """Store or update a GitHub token for a Slack user"""
    github_tokens_collection.update_one(
        {"slack_user_id": slack_user_id},
        {"$set": {
            "github_token": github_token,
            "updated_at": datetime.now()
        }},
        upsert=True
    )

def get_github_token(slack_user_id: str) -> str:
    """Retrieve a GitHub token for a Slack user"""
    token_doc = github_tokens_collection.find_one({"slack_user_id": slack_user_id})
    return token_doc["github_token"] if token_doc else None

def delete_github_token(slack_user_id: str):
    """Remove a GitHub token for a Slack user"""
    github_tokens_collection.delete_one({"slack_user_id": slack_user_id})
