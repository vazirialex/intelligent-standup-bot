from pymongo import MongoClient
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client["standup_db"]
updates_collection = db["daily_updates"]
messages_collection = db["messages"]

def get_standup_updates_by_user_id(user_id: str, date = None):
    """
    Get standup updates for a user on a given date
    """
    db_query = {"user_id": user_id, "date": date} if date else {"user_id": user_id}
    updates = list(updates_collection.find(db_query, {"_id": 0}))
    if updates:
        return updates[0]
    raise Exception("No updates found for user")

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
    pass

def standup_message_sent(user_id, date = None):
    return True

def save_message_to_db(user_id, message, channel_id, is_bot):
    messages_collection.insert_one({
        "type": "message",
        "is_bot": is_bot,
        "user_id": user_id,
        "message": message,
        "channel_id": channel_id,
        "timestamp": datetime.now()
    })

def get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=10):
    result = list(messages_collection.find({"user_id": user_id, "channel_id": channel_id}, {"_id": 0}).sort("timestamp", -1))[:max_number_of_messages_to_fetch]
    print("slack messages from db: ", result)
    return result


