from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging
import motor.motor_asyncio
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
import asyncio
from .config import MONGODB_URI, DATABASE_NAME, COLLECTIONS

logger = logging.getLogger('discord')

class DatabaseManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not DatabaseManager._initialized:
            if not MONGODB_URI:
                raise ValueError("MongoDB URI not found in environment variables")
            
            # Initialize async client
            self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
            self.db = self.client[DATABASE_NAME]
            
            # Initialize collections
            self.tickets = self.db[COLLECTIONS['tickets']]
            self.ticket_messages = self.db[COLLECTIONS['ticket_messages']]
            self.feedback = self.db[COLLECTIONS['feedback']]
            self.staff_roles = self.db[COLLECTIONS['staff_roles']]
            self.user_tickets = self.db[COLLECTIONS['user_tickets']]
            self.ticket_logs = self.db[COLLECTIONS['ticket_logs']]
            self.bot_config = self.db[COLLECTIONS['bot_config']]
            
            # Create indexes
            asyncio.create_task(self._create_indexes())
            DatabaseManager._initialized = True

    async def _create_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # Tickets collection indexes
            await self.tickets.create_index([("user_id", ASCENDING)])
            await self.tickets.create_index([("status", ASCENDING)])
            await self.tickets.create_index([("created_at", DESCENDING)])
            
            # Messages collection indexes
            await self.ticket_messages.create_index([("ticket_number", ASCENDING)])
            await self.ticket_messages.create_index([("timestamp", ASCENDING)])
            
            # User tickets collection indexes
            await self.user_tickets.create_index([("user_id", ASCENDING)], unique=True)
            
            logger.info("Database indexes created successfully")
        except PyMongoError as e:
            logger.error(f"Error creating database indexes: {e}")

    async def create_ticket(self, ticket_data: Dict[str, Any]) -> Optional[str]:
        """Create a new ticket in the database"""
        try:
            result = await self.tickets.insert_one(ticket_data)
            if result.inserted_id:
                return str(ticket_data['ticket_number'])
            return None
        except PyMongoError as e:
            logger.error(f"Error creating ticket: {e}")
            return None

    async def get_next_ticket_number(self) -> str:
        """Get the next available ticket number"""
        try:
            latest_ticket = await self.tickets.find_one(
                sort=[("ticket_number", DESCENDING)]
            )
            if latest_ticket:
                return str(int(latest_ticket['ticket_number']) + 1)
            return "10000"
        except PyMongoError as e:
            logger.error(f"Error getting next ticket number: {e}")
            return str(10000)

    async def has_open_ticket(self, user_id: str) -> bool:
        """Check if a user has any open tickets"""
        try:
            count = await self.tickets.count_documents({
                "user_id": user_id,
                "status": "open"
            })
            return count > 0
        except PyMongoError as e:
            logger.error(f"Error checking open tickets: {e}")
            return False

    async def get_ticket(self, ticket_number: str) -> Optional[Dict[str, Any]]:
        """Get ticket by number"""
        try:
            return await self.tickets.find_one({"ticket_number": ticket_number})
        except PyMongoError as e:
            logger.error(f"Error getting ticket: {e}")
            return None

    async def update_ticket(self, ticket_number: str, update_data: Dict[str, Any]) -> bool:
        """Update ticket data"""
        try:
            result = await self.tickets.update_one(
                {"ticket_number": ticket_number},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error updating ticket: {e}")
            return False

    async def store_message(self, message_data: Dict[str, Any]) -> bool:
        """Store a ticket message"""
        try:
            result = await self.ticket_messages.insert_one(message_data)
            return bool(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Error storing message: {e}")
            return False

    async def get_ticket_messages(self, ticket_number: str) -> List[Dict[str, Any]]:
        """Get all messages for a ticket"""
        try:
            cursor = self.ticket_messages.find(
                {"ticket_number": ticket_number}
            ).sort("timestamp", ASCENDING)
            return await cursor.to_list(length=None)
        except PyMongoError as e:
            logger.error(f"Error getting ticket messages: {e}")
            return []

    async def store_feedback(self, feedback_data: Dict[str, Any]) -> bool:
        """Store ticket feedback"""
        try:
            result = await self.feedback.insert_one(feedback_data)
            return bool(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Error storing feedback: {e}")
            return False

    async def get_feedback(self, ticket_number: str) -> Optional[Dict[str, Any]]:
        """Get feedback for a ticket"""
        try:
            return await self.feedback.find_one({"ticket_number": ticket_number})
        except PyMongoError as e:
            logger.error(f"Error getting feedback: {e}")
            return None

    async def close_ticket(self, ticket_number: str) -> bool:
        """Close a ticket"""
        try:
            result = await self.tickets.update_one(
                {"ticket_number": ticket_number},
                {
                    "$set": {
                        "status": "closed",
                        "closed_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error closing ticket: {e}")
            return False

    async def cleanup_old_tickets(self, max_age_days: int = 30) -> int:
        """Clean up old tickets"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            result = await self.tickets.delete_many({
                "status": "closed",
                "closed_at": {"$lt": cutoff_date}
            })
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Error cleaning up tickets: {e}")
            return 0
