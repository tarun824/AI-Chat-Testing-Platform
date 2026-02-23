from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from app.config import MONGO_URI, MONGO_DB

_client = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        if not MONGO_URI:
            raise RuntimeError("MONGO_URI is not set")
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client


def get_db():
    client = get_client()
    return client[MONGO_DB]


def get_collection(name: str):
    db = get_db()
    return db[name]


def to_object_id(value: str) -> ObjectId:
    return ObjectId(value)
