from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["standup_db"]
updates_collection = db["daily_updates"]

def get_updates_by_id(user_id: str):
    updates = list(updates_collection.find({"user_id": user_id}, {"_id": 0}))
    if updates:
        return updates
    raise HTTPException(status_code=404, detail="No updates found for user")

def insert_item(user_id, extracted_updates, now_pst):
    updates_collection.insert_one({
            "user_id": user_id,
            "updates": extracted_updates,
            "timestamp": now_pst
        })