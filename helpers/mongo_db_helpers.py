from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["standup_db"]
updates_collection = db["daily_updates"]

def get_updates_by_id(user_id: str):
    updates = list(updates_collection.find({"user_id": user_id}, {"_id": 0}))
    if updates:
        return updates
    raise HTTPException(status_code=404, detail="No updates found for user")

def insert_item(user_id, extracted_updates):
    now = datetime.now()
    date = datetime.strptime(now, "%Y-%m-%d")
    updates_collection.insert_one({
        "user_id": user_id,
        "updates": extracted_updates,
        "date": date,
        "update_time": now
    })

def update_exists(user_id, date = None):
    desired_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.strptime(datetime.now(), "%Y-%m-%d")
    return updates_collection.find_one({"user_id": user_id, "date": desired_date}) is not None

def update_item(user_id, extracted_updates):
    now = datetime.now()
    date = datetime.strptime(now, "%Y-%m-%d")
    updates_collection.update_one(
        {"user_id": user_id, "date": date},
        {"$set": {"updates": extracted_updates, "update_time": now}}
    )

def delete_item(user_id, date = None):
    desired_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.strptime(datetime.now(), "%Y-%m-%d")
    updates_collection.delete_one({"user_id": user_id, "date": desired_date})

def persist_scheduled_message(user_id, message, scheduled_time):
    pass

def standup_message_sent(user_id, date = None):
    return True