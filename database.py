import motor.motor_asyncio
from config import MONGO_URL

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client['TelegramManagerBot']
users_collection = db['users']

async def add_session(phone_number: str, session_string: str):
    await users_collection.update_one(
        {"phone": phone_number},
        {"$set": {"session": session_string, "status": "active"}},
        upsert=True
    )

async def get_all_sessions():
    return await users_collection.find({"status": "active"}).to_list(length=None)

async def count_sessions():
    return await users_collection.count_documents({"status": "active"})
