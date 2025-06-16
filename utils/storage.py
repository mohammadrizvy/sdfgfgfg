import random
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from threading import Lock
import json
import os

logger = logging.getLogger('discord')

_db_manager = None # Global variable to hold the DatabaseManager instance

def set_db_manager(db_manager_instance):
    global _db_manager
    _db_manager = db_manager_instance
    logger.info("DatabaseManager instance set in storage.py")

# File paths
CONFIG_FILE = 'config.json'
USERS_FILE = 'users.json'
TICKET_LOGS_FILE = 'ticket_logs.json'

def log_operation(operation: str, details: dict) -> None:
    """Helper function for consistent logging"""
    try:
        log_msg = f"[{operation}] " + " | ".join(f"{k}: {v}" for k, v in details.items())
        logger.info(log_msg)
    except Exception as e:
        logger.error(f"Error in logging: {e}")

# In-memory storage data
tickets: Dict[str, Dict[str, Any]] = {}  # Store ticket information
feedback_storage: Dict[str, Dict[str, Any]] = {}  # Store feedback information
ticket_logs: Dict[str, Dict[str, Any]] = {}  # Store ticket logs
ticket_counter: int = 10000  # Starting ticket number

# Add thread safety for ticket counter and logs
ticket_counter_lock = Lock()
ticket_logs_lock = Lock()

# Define carry service categories and their roles
CATEGORY_ROLES = {
    "Slayer Carry": "Slayer Carrier",
    "Normal Dungeon Carry": "Normal Dungeon Carrier", 
    "Master Dungeon Carry": "Master Dungeon Carrier",
    "Support Tickets": "Support Staff",
    "Bug Reports": "Developer",
    "Ban Appeals": "Moderator"
}

def get_category_role(category: str) -> Optional[str]:
    """Get the staff role name associated with a ticket category"""
    return CATEGORY_ROLES.get(category)

# Embed colors for carry services
CATEGORY_COLORS = {
    "Slayer Carry": 0xff0000,  # Red
    "Normal Dungeon Carry": 0x0099ff,  # Blue
    "Master Dungeon Carry": 0x9900ff,  # Purple
    "Support Tickets": 0x00ff00,  # Green
    "Bug Reports": 0xff6b6b,  # Light Red
    "Ban Appeals": 0x4834d4,  # Purple Blue
}

def get_category_color(category: str) -> int:
    """Get the color associated with a ticket category"""
    return CATEGORY_COLORS.get(category, 0x7289DA)  # Default Discord blue if category not found

async def get_next_ticket_number() -> str:
    """Get next sequential ticket number with thread safety"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return "10000" # Fallback
    try:
        # MongoDB handles sequential numbering or we can implement logic based on latest ticket
        return await _db_manager.get_next_ticket_number()
    except Exception as e:
        logger.error(f"Error getting next ticket number from DB: {e}")
        return "10000" # Fallback

async def has_open_ticket(user_id: str) -> bool:
    """Check if a user has any open tickets"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return False
    try:
        return await _db_manager.has_open_ticket(user_id)
    except Exception as e:
        logger.error(f"Error checking open tickets in DB: {e}")
        return False

async def get_user_ticket_channel(user_id: str) -> Optional[str]:
    """Get the channel ID of user's open ticket if exists"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return None
    try:
        ticket = await _db_manager.tickets.find_one({"user_id": user_id, "status": "open"})
        return ticket.get('channel_id') if ticket else None
    except Exception as e:
        logger.error(f"Error getting user ticket channel from DB: {e}")
        return None

async def create_ticket(ticket_number: str, user_id: str, channel_id: str, category: str, details: str, guild_id: int, control_message_id: Optional[int] = None) -> bool:
    """Create a new ticket and store it"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return False

    if not validate_ticket_input(ticket_number, user_id, channel_id, category):
        return False

    ticket_info = {
        "ticket_number": ticket_number,
        "user_id": user_id,
        "channel_id": channel_id,
        "category": category,
        "details": details,
        "guild_id": guild_id,
        "status": "open",
        "claimed_by": "Unclaimed", # Default to unclaimed
        "created_at": datetime.now(timezone.utc).isoformat(),
        "control_message_id": control_message_id # Store the message ID for persistent views
    }
    try:
        return await _db_manager.create_ticket(ticket_info)
    except Exception as e:
        logger.error(f"Error creating ticket in DB: {e}")
        return False

async def claim_ticket(ticket_number: str, claimer: str) -> bool:
    """Claim or unclaim a ticket"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return False
    try:
        update_data = {
            "claimed_by": claimer,
            "claimed_time": datetime.now(timezone.utc).isoformat() if claimer != "Unclaimed" else None,
            "claimed_timestamp": datetime.now(timezone.utc).timestamp() if claimer != "Unclaimed" else None
        }
        return await _db_manager.update_ticket(ticket_number, update_data)
    except Exception as e:
        logger.error(f"Error claiming ticket in DB: {e}")
        return False

async def get_ticket_claimed_by(ticket_number: str) -> str:
    """Get who claimed a ticket"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return 'Unclaimed'
    try:
        ticket = await _db_manager.get_ticket(ticket_number)
        if ticket:
            return ticket.get('claimed_by', 'Unclaimed')
        return 'Unclaimed'
    except Exception as e:
        logger.error(f"Error getting ticket claimer from DB: {e}")
        return 'Unclaimed'

def store_feedback(ticket_name: str, user_id: str, rating: int, feedback: str, suggestions: str = "", carrier_ratings: dict = None) -> bool:
    """Store feedback for a ticket"""
    try:
        feedback_data = {
            "ticket_number": ticket_name,
            "user_id": user_id,
            "rating": rating,
            "feedback": feedback,
            "suggestions": suggestions or "",
            "carrier_ratings": carrier_ratings or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "submitted_at": datetime.now(timezone.utc).isoformat()
        }
        feedback_storage[ticket_name] = feedback_data
        log_operation("STORE_FEEDBACK", {
            "ticket_number": ticket_name,
            "user_id": user_id,
            "rating": rating
        })
        return True
    except Exception as e:
        logger.error(f"Error storing feedback: {e}")
        return False

def get_feedback(ticket_name: str) -> Dict[str, Any]:
    """Get feedback for a ticket"""
    try:
        feedback = feedback_storage.get(ticket_name, {})
        if feedback:
            log_operation("GET_FEEDBACK", {"ticket_number": ticket_name, "found": True})
        else:
            log_operation("GET_FEEDBACK", {"ticket_number": ticket_name, "found": False})
        return feedback
    except Exception as e:
        logger.error(f"Error retrieving feedback: {e}")
        return {}

async def store_ticket_log(ticket_number: str, messages: list, creator_id: str, category: str,
                       claimed_by: Optional[str] = None, closed_by: Optional[str] = None,
                       details: Optional[str] = None, guild_id: Optional[int] = None,
                       close_reason: Optional[str] = None) -> bool:
    """Store a comprehensive ticket log entry in the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return False

    log_entry = {
        "ticket_number": ticket_number,
        "messages": messages,
        "creator_id": creator_id,
        "category": category,
        "claimed_by": claimed_by,
        "closed_by": closed_by,
        "details": details,
        "guild_id": guild_id,
        "close_reason": close_reason,
        "logged_at": datetime.now(timezone.utc).isoformat() # Timestamp for when the log was stored
    }
    try:
        # Check if a log for this ticket already exists to decide between insert and update
        existing_log = await _db_manager.ticket_logs.find_one({"ticket_number": ticket_number})
        if existing_log:
            result = await _db_manager.ticket_logs.update_one(
                {"ticket_number": ticket_number},
                {"$set": log_entry}
            )
            log_operation("UPDATE_TICKET_LOG_DB", {"ticket_number": ticket_number})
            return result.modified_count > 0
        else:
            result = await _db_manager.ticket_logs.insert_one(log_entry)
            log_operation("STORE_TICKET_LOG_DB", {"ticket_number": ticket_number})
            return bool(result.inserted_id)
    except Exception as e:
        logger.error(f"Error storing ticket log in DB: {e}")
        return False

async def get_ticket_log(ticket_number: str) -> Optional[Dict[str, Any]]:
    """Get a specific ticket log entry"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return None
    try:
        return await _db_manager.get_ticket(ticket_number)
    except Exception as e:
        logger.error(f"Error getting ticket log from DB: {e}")
        return None

async def get_ticket(ticket_number: str) -> Optional[Dict[str, Any]]:
    """Get a specific ticket by its number from the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return None
    try:
        return await _db_manager.get_ticket(ticket_number)
    except Exception as e:
        logger.error(f"Error getting ticket from DB: {e}")
        return None

async def close_ticket(ticket_number: str, close_reason: Optional[str] = None) -> bool:
    """Close a ticket and remove it from active tracking"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return False
    try:
        update_data = {
            "status": "closed",
            "close_reason": close_reason or "Completed",
            "closed_at": datetime.now(timezone.utc).isoformat()
        }
        return await _db_manager.update_ticket(ticket_number, update_data)
    except Exception as e:
        logger.error(f"Error closing ticket in DB: {e}")
        return False

async def update_ticket_times(ticket_number: str, event_type: str, user_id: str = None) -> bool:
    """Update timing information for a ticket (created, first_response, claimed, resolved)"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return False
    try:
        update_data = {}
        current_time_iso = datetime.now(timezone.utc).isoformat()
        current_timestamp = datetime.now(timezone.utc).timestamp()

        if event_type == "created":
            update_data["created_at"] = current_time_iso
            update_data["created_timestamp"] = current_timestamp
        elif event_type == "first_response":
            update_data["first_response_time"] = current_time_iso
            update_data["first_response_timestamp"] = current_timestamp
            update_data["first_responder_id"] = user_id
        elif event_type == "claimed":
            update_data["claimed_time"] = current_time_iso
            update_data["claimed_timestamp"] = current_timestamp
            update_data["claimer_id"] = user_id
        elif event_type == "resolved":
            update_data["resolution_time"] = current_time_iso
            update_data["resolution_timestamp"] = current_timestamp
            update_data["resolver_id"] = user_id

        if update_data:
            return await _db_manager.update_ticket(ticket_number, update_data)
        return False
    except Exception as e:
        logger.error(f"Error updating ticket times in DB: {e}")
        return False

def get_ticket_waiting_time(ticket_number: str) -> str:
    """Get formatted waiting time for a ticket with high precision"""
    try:
        if ticket_number not in tickets:
            return "Unknown"
            
        ticket = tickets[ticket_number]
        current_time = datetime.now(timezone.utc)
        current_timestamp = current_time.timestamp()
        
        # Get creation timestamp
        created_timestamp = ticket.get("created_timestamp")
        if not created_timestamp:
            # Fallback to parsing created_at if timestamp not available
            try:
                created_at = datetime.fromisoformat(ticket.get("created_at"))
                created_timestamp = created_at.timestamp()
            except:
                return "Unknown"
        
        # If there's a first response, use that as the end time
        if ticket.get("first_response_timestamp"):
            end_timestamp = ticket.get("first_response_timestamp")
        else:
            end_timestamp = current_timestamp
            
        waiting_time = end_timestamp - created_timestamp
        
        # Format the waiting time with high precision
        if waiting_time < 60:
            return f"{waiting_time:.1f} seconds"
        elif waiting_time < 3600:
            minutes = waiting_time / 60
            return f"{minutes:.1f} minute{'s' if minutes != 1 else ''}"
        elif waiting_time < 86400:
            hours = waiting_time / 3600
            return f"{hours:.1f} hour{'s' if hours != 1 else ''}"
        else:
            days = waiting_time / 86400
            return f"{days:.1f} day{'s' if days != 1 else ''}"
            
    except Exception as e:
        logger.error(f"Error getting ticket waiting time: {e}")
        return "Unknown"

def get_ticket_stats(ticket_number: str) -> dict:
    """Get detailed statistics for a ticket"""
    try:
        if ticket_number not in tickets:
            return {}
            
        ticket = tickets[ticket_number]
        stats = {
            "ticket_number": ticket_number,
            "category": ticket.get("category", "Unknown"),
            "status": ticket.get("status", "Unknown"),
            "created_at": ticket.get("created_at"),
            "claimed_by": ticket.get("claimed_by", "Unclaimed"),
            "claimed_time": ticket.get("claimed_time"),
            "first_response_time": ticket.get("first_response_time"),
            "resolution_time": ticket.get("resolution_time"),
            "response_duration": ticket.get("response_duration", 0),
            "resolution_duration": ticket.get("resolution_duration", 0),
            "creator_id": ticket.get("creator_id"),
            "claimer_id": ticket.get("claimer_id"),
            "responder_id": ticket.get("responder_id"),
            "resolver_id": ticket.get("resolver_id")
        }
        
        return stats
    except Exception as e:
        logger.error(f"Error getting ticket stats: {e}")
        return {}

def validate_ticket_input(ticket_number: str, user_id: str, channel_id: str, category: str) -> bool:
    """Validate input parameters for ticket creation"""
    try:
        if not all([ticket_number, user_id, channel_id, category]):
            logger.error("Missing required ticket parameters")
            return False
        if not ticket_number.isdigit():
            logger.error(f"Invalid ticket number format: {ticket_number}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error validating ticket input: {e}")
        return False

async def get_all_tickets() -> List[Dict[str, Any]]:
    """Get all tickets from the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return []
    try:
        return await _db_manager.tickets.find({}).to_list(None)
    except Exception as e:
        logger.error(f"Error getting all tickets from DB: {e}")
        return []

async def get_tickets_by_status(status: str) -> List[Dict[str, Any]]:
    """Get tickets by status from the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return []
    try:
        return await _db_manager.tickets.find({"status": status}).to_list(None)
    except Exception as e:
        logger.error(f"Error getting tickets by status from DB: {e}")
        return []

async def get_tickets_by_user(user_id: str) -> List[Dict[str, Any]]:
    """Get all tickets for a specific user from the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return []
    try:
        return await _db_manager.tickets.find({"user_id": user_id}).to_list(None)
    except Exception as e:
        logger.error(f"Error getting tickets by user from DB: {e}")
        return []

async def get_tickets_by_category(category: str) -> List[Dict[str, Any]]:
    """Get tickets by category from the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return []
    try:
        return await _db_manager.tickets.find({"category": category}).to_list(None)
    except Exception as e:
        logger.error(f"Error getting tickets by category from DB: {e}")
        return []

async def update_ticket(ticket_number: str, updates: Dict[str, Any]) -> bool:
    """Update ticket information in the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return False
    try:
        return await _db_manager.update_ticket(ticket_number, updates)
    except Exception as e:
        logger.error(f"Error updating ticket in DB: {e}")
        return False

async def get_ticket_statistics() -> Dict[str, Any]:
    """Get ticket statistics from the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return {}
    try:
        all_tickets = await _db_manager.tickets.find({}).to_list(None)
        all_feedback = await _db_manager.feedback.find({}).to_list(None)

        stats = {
            "total_tickets": len(all_tickets),
            "open_tickets": len([t for t in all_tickets if t.get('status') == 'open']),
            "closed_tickets": len([t for t in all_tickets if t.get('status') == 'closed']),
            "claimed_tickets": len([t for t in all_tickets if t.get('claimed_by') != 'Unclaimed']),
            "categories": {},
            "total_feedback": len(all_feedback),
            "average_rating": 0.0
        }

        # Category statistics
        for ticket in all_tickets:
            category = ticket.get('category', 'Unknown')
            if category not in stats['categories']:
                stats['categories'][category] = {
                    'total': 0,
                    'open': 0,
                    'closed': 0,
                    'claimed': 0
                }
            stats['categories'][category]['total'] += 1
            if ticket.get('status') == 'open':
                stats['categories'][category]['open'] += 1
            elif ticket.get('status') == 'closed':
                stats['categories'][category]['closed'] += 1
            if ticket.get('claimed_by') != 'Unclaimed':
                stats['categories'][category]['claimed'] += 1

        # Calculate average rating
        if all_feedback:
            ratings = [f.get('rating', 0) for f in all_feedback if f.get('rating')]
            if ratings:
                stats['average_rating'] = sum(ratings) / len(ratings)

        return stats
    except Exception as e:
        logger.error(f"Error getting ticket statistics from DB: {e}")
        return {}

async def export_data() -> Dict[str, Any]:
    """Export all data for backup purposes from the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return {}
    try:
        all_tickets = await _db_manager.tickets.find({}).to_list(None)
        all_feedback = await _db_manager.feedback.find({}).to_list(None)
        all_ticket_logs = await _db_manager.ticket_logs.find({}).to_list(None)
        
        return {
            "tickets": all_tickets,
            "feedback": all_feedback,
            "ticket_logs": all_ticket_logs,
            "export_timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error exporting data from DB: {e}")
        return {}

async def import_data(data: Dict[str, Any]) -> bool:
    """Import data from backup into the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return False
    try:
        # Clear existing data in collections before importing
        await _db_manager.tickets.delete_many({})
        await _db_manager.feedback.delete_many({})
        await _db_manager.ticket_logs.delete_many({})

        # Insert new data
        if 'tickets' in data and data['tickets']:
            await _db_manager.tickets.insert_many(data['tickets'])
        if 'feedback' in data and data['feedback']:
            await _db_manager.feedback.insert_many(data['feedback'])
        if 'ticket_logs' in data and data['ticket_logs']:
            await _db_manager.ticket_logs.insert_many(data['ticket_logs'])
        
        log_operation("IMPORT_DATA_DB", {
            "tickets_imported": len(data.get('tickets', {})),
            "feedback_imported": len(data.get('feedback', {})),
            "ticket_logs_imported": len(data.get('ticket_logs', {}))
        })
        return True
    except Exception as e:
        logger.error(f"Error importing data to DB: {e}")
        return False

async def search_tickets(query: str, search_in: List[str] = None) -> List[Dict[str, Any]]:
    """Search tickets by query in the database"""
    if _db_manager is None:
        logger.error("Database manager not set in storage module.")
        return []
    try:
        if search_in is None:
            search_in = ['category', 'details', 'user_id', 'claimed_by']
        
        # Build a MongoDB OR query for flexible searching
        search_filters = []
        query_regex = {"$regex": query, "$options": "i"} # Case-insensitive search

        for field in search_in:
            search_filters.append({field: query_regex})
        
        if not search_filters:
            return []

        results = await _db_manager.tickets.find({"$or": search_filters}).to_list(None)
        
        log_operation("SEARCH_TICKETS_DB", {
            "query": query,
            "search_in": search_in,
            "results_count": len(results)
        })
        return results
    except Exception as e:
        logger.error(f"Error searching tickets in DB: {e}")
        return []

def cleanup_old_tickets(max_age_days: int = 30) -> int:
    """Clean up tickets older than max_age_days. Returns number of tickets cleaned."""
    try:
        current_time = datetime.now(timezone.utc)
        max_age = timedelta(days=max_age_days)
        cleaned_count = 0

        # Find tickets to clean up
        for ticket_number, ticket_data in list(tickets.items()):
            try:
                created_at_str = ticket_data.get('created_at')
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    
                    if (current_time - created_at) > max_age and ticket_data.get('status') == 'closed':
                        # Archive ticket data to logs before removing
                        if ticket_number not in ticket_logs:
                            store_ticket_log(
                                ticket_number=ticket_number,
                                messages=[],
                                creator_id=ticket_data['user_id'],
                                category=ticket_data['category'],
                                details="Auto-archived due to age"
                            )
                        del tickets[ticket_number]
                        cleaned_count += 1
            except Exception as ticket_e:
                logger.error(f"Error processing ticket {ticket_number} for cleanup: {ticket_e}")
                continue

        if cleaned_count > 0:
            log_operation("CLEANUP_TICKETS", {
                "cleaned_count": cleaned_count,
                "max_age_days": max_age_days
            })

        return cleaned_count
    except Exception as e:
        logger.error(f"Error cleaning up old tickets: {e}")
        return 0

# Enhanced Storage Class for file-based persistence (optional)
class EnhancedStorage:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.tickets_file = os.path.join(self.data_dir, "tickets.json")
        self.feedback_file = os.path.join(self.data_dir, "feedback.json")
        self.logs_file = os.path.join(self.data_dir, "ticket_logs.json")
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        try:
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir)
                logger.info(f"Created data directory: {self.data_dir}")
        except Exception as e:
            logger.error(f"Error creating data directory: {e}")

    def save_all_data(self) -> bool:
        """Save all data to files"""
        try:
            # Save tickets
            with open(self.tickets_file, 'w') as f:
                json.dump(tickets, f, indent=2, default=str)
            
            # Save feedback
            with open(self.feedback_file, 'w') as f:
                json.dump(feedback_storage, f, indent=2, default=str)
            
            # Save logs
            with open(self.logs_file, 'w') as f:
                json.dump(ticket_logs, f, indent=2, default=str)
                
            log_operation("SAVE_ALL_DATA", {"success": True})
            return True
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            return False

    def load_all_data(self) -> bool:
        """Load all data from files"""
        try:
            global tickets, feedback_storage, ticket_logs, ticket_counter
            
            # Load tickets
            if os.path.exists(self.tickets_file):
                with open(self.tickets_file, 'r') as f:
                    loaded_tickets = json.load(f)
                    tickets.update(loaded_tickets)
            
            # Load feedback
            if os.path.exists(self.feedback_file):
                with open(self.feedback_file, 'r') as f:
                    loaded_feedback = json.load(f)
                    feedback_storage.update(loaded_feedback)
            
            # Load logs
            if os.path.exists(self.logs_file):
                with open(self.logs_file, 'r') as f:
                    loaded_logs = json.load(f)
                    ticket_logs.update(loaded_logs)
            
            log_operation("LOAD_ALL_DATA", {
                "tickets_loaded": len(tickets),
                "feedback_loaded": len(feedback_storage)
            })
            return True
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False

# Create global enhanced storage instance
enhanced_storage = EnhancedStorage()

def save_data_to_file() -> bool:
    """Save all data to files using enhanced storage"""
    return enhanced_storage.save_all_data()

def load_data_from_file() -> bool:
    """Load all data from files using enhanced storage"""
    return enhanced_storage.load_all_data()

# Add with other global variables
users: Dict[str, dict] = {}

def add_user(user_data: dict) -> bool:
    """Add a new user to the system"""
    try:
        user_id = user_data.get("user_id")
        if not user_id:
            logger.error("Missing user_id in user data")
            return False

        # Check if user already exists
        if user_id in users:
            logger.warning(f"User {user_id} already exists")
            return False

        # Add user to storage
        users[user_id] = user_data

        # Save to file
        save_users_to_file()

        logger.info(f"User {user_data.get('username')} (ID: {user_id}) added successfully")
        return True

    except Exception as e:
        logger.error(f"Error adding user: {e}")
        return False

def save_users_to_file():
    """Save users data to a JSON file"""
    try:
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        file_path = os.path.join(data_dir, 'users.json')
        with open(file_path, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving users to file: {e}")

def load_users_from_file():
    """Load users data from JSON file"""
    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'users.json')
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                global users
                users = json.load(f)
    except Exception as e:
        logger.error(f"Error loading users from file: {e}")

# Add this to the initialization code
load_users_from_file()

def get_confirmation_message():
    """Get the confirmation message for ticket creation"""
    return "✅ Your request has been submitted! A ticket will be created shortly."