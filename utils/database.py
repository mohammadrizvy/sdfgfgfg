from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging
import motor.motor_asyncio
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
import asyncio
import os
from .config import MONGODB_URI, DATABASE_NAME, COLLECTIONS
import sqlite3
import json
import aiosqlite

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
            # Get MongoDB URI from environment or use default
            mongo_uri = MONGODB_URI or os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
            
            # Initialize async client
            self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
            self.db = self.client[DATABASE_NAME]
            
            # Initialize collections
            self.tickets = self.db[COLLECTIONS['tickets']]
            self.ticket_messages = self.db[COLLECTIONS['ticket_messages']]
            self.feedback = self.db[COLLECTIONS['feedback']]
            self.staff_roles = self.db[COLLECTIONS['staff_roles']]
            self.user_tickets = self.db[COLLECTIONS['user_tickets']]
            self.ticket_logs = self.db[COLLECTIONS['ticket_logs']]
            self.bot_config = self.db[COLLECTIONS['bot_config']]
            
            self.db_path = 'data/tickets.db'
            self.backup_dir = 'backups'
            os.makedirs('data', exist_ok=True)
            os.makedirs(self.backup_dir, exist_ok=True)
            
            DatabaseManager._initialized = True
    
    async def connect(self):
        """Establish database connection and create indexes"""
        try:
            # Test connection
            await self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            # Create indexes
            await self._create_indexes()

            self.conn = await aiosqlite.connect(self.db_path)
            await self.create_tables()
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False

    async def _create_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # Tickets collection indexes
            await self.tickets.create_index([("user_id", ASCENDING)])
            await self.tickets.create_index([("status", ASCENDING)])
            await self.tickets.create_index([("created_at", DESCENDING)])
            await self.tickets.create_index([("ticket_number", ASCENDING)], unique=True)
            
            # Messages collection indexes
            await self.ticket_messages.create_index([("ticket_number", ASCENDING)])
            await self.ticket_messages.create_index([("timestamp", ASCENDING)])
            
            # User tickets collection indexes
            await self.user_tickets.create_index([("user_id", ASCENDING)], unique=True)
            
            logger.info("Database indexes created successfully")
        except PyMongoError as e:
            logger.error(f"Error creating database indexes: {e}")

    async def create_tables(self):
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tickets (
                        ticket_number INTEGER PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        category TEXT NOT NULL,
                        description TEXT,
                        channel_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        closed_at TIMESTAMP,
                        control_message_id TEXT
                    )
                ''')

                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ticket_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                ''')

                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ticket_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_number INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        user TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (ticket_number) REFERENCES tickets (ticket_number)
                    )
                ''')

                await self.conn.commit()
                logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise

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
            async with self.conn.cursor() as cursor:
                await cursor.execute("SELECT MAX(ticket_number) FROM tickets")
                result = await cursor.fetchone()
                return str((result[0] or 0) + 1)
        except Exception as e:
            logger.error(f"Error getting next ticket number: {e}")
            raise

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
                        "closed_at": datetime.now(timezone.utc).isoformat()
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
                "closed_at": {"$lt": cutoff_date.isoformat()}
            })
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Error cleaning up tickets: {e}")
            return 0

    async def get_all_open_tickets(self) -> List[Dict[str, Any]]:
        """Get all tickets that are currently open"""
        try:
            cursor = self.tickets.find({"status": {"$ne": "closed"}})
            return await cursor.to_list(None)
        except PyMongoError as e:
            logger.error(f"Error getting all open tickets: {e}")
            return []

    async def get_user_ticket_channel(self, user_id: str) -> Optional[str]:
        """Get the channel ID of user's open ticket if exists"""
        try:
            ticket = await self.tickets.find_one({
                "user_id": user_id, 
                "status": "open"
            })
            return ticket.get('channel_id') if ticket else None
        except PyMongoError as e:
            logger.error(f"Error getting user ticket channel: {e}")
            return None

    async def get_ticket_info(self, ticket_number):
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('''
                    SELECT * FROM tickets WHERE ticket_number = ?
                ''', (ticket_number,))
                result = await cursor.fetchone()
                
                if result:
                    return {
                        'ticket_number': result[0],
                        'user_id': result[1],
                        'category': result[2],
                        'description': result[3],
                        'channel_id': result[4],
                        'status': result[5],
                        'created_at': result[6],
                        'closed_at': result[7],
                        'control_message_id': result[8]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting ticket info: {e}")
            raise

    async def get_all_closed_tickets(self):
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('''
                    SELECT * FROM tickets WHERE status = 'closed'
                ''')
                results = await cursor.fetchall()
                
                tickets = []
                for result in results:
                    tickets.append({
                        'ticket_number': result[0],
                        'user_id': result[1],
                        'category': result[2],
                        'description': result[3],
                        'channel_id': result[4],
                        'status': result[5],
                        'created_at': result[6],
                        'closed_at': result[7],
                        'control_message_id': result[8]
                    })
                return tickets
        except Exception as e:
            logger.error(f"Error getting closed tickets: {e}")
            raise

    async def get_ticket_stats(self):
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('''
                    SELECT 
                        COUNT(*) as total_tickets,
                        SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_tickets,
                        SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_tickets
                    FROM tickets
                ''')
                result = await cursor.fetchone()
                
                return {
                    'total_tickets': result[0],
                    'open_tickets': result[1],
                    'closed_tickets': result[2]
                }
        except Exception as e:
            logger.error(f"Error getting ticket stats: {e}")
            raise

    async def log_ticket_action(self, ticket_number, action, user):
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('''
                    INSERT INTO ticket_logs (ticket_number, action, user)
                    VALUES (?, ?, ?)
                ''', (ticket_number, action, user))
                await self.conn.commit()
        except Exception as e:
            logger.error(f"Error logging ticket action: {e}")
            raise

    async def get_recent_logs(self, limit=10):
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('''
                    SELECT ticket_number, action, user, timestamp
                    FROM ticket_logs
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
                results = await cursor.fetchall()
                
                logs = []
                for result in results:
                    logs.append({
                        'ticket_number': result[0],
                        'action': result[1],
                        'user': result[2],
                        'timestamp': result[3]
                    })
                return logs
        except Exception as e:
            logger.error(f"Error getting recent logs: {e}")
            raise

    async def get_ticket_settings(self):
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('SELECT key, value FROM ticket_settings')
                results = await cursor.fetchall()
                
                settings = {}
                for result in results:
                    settings[result[0]] = result[1]
                return settings
        except Exception as e:
            logger.error(f"Error getting ticket settings: {e}")
            raise

    async def update_ticket_setting(self, key, value):
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('''
                    INSERT OR REPLACE INTO ticket_settings (key, value)
                    VALUES (?, ?)
                ''', (key, value))
                await self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating ticket setting: {e}")
            return False

    async def create_backup(self):
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(self.backup_dir, f'tickets_backup_{timestamp}.db')
            
            async with aiosqlite.connect(self.db_path) as source:
                async with aiosqlite.connect(backup_path) as dest:
                    await source.backup(dest)
            
            logger.info(f"Database backup created at {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            return None

    async def restore_backup(self, backup_file):
        try:
            backup_path = os.path.join(self.backup_dir, backup_file)
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            async with aiosqlite.connect(backup_path) as source:
                async with aiosqlite.connect(self.db_path) as dest:
                    await source.backup(dest)
            
            logger.info(f"Database restored from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error restoring database backup: {e}")
            return False

    async def close(self):
        try:
            await self.conn.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
            raise