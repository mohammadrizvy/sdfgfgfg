import random
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from threading import Lock
import json
import os

logger = logging.getLogger('discord')

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
    "Staff Applications": "Admin",
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
    "Staff Applications": 0xffa500,  # Orange
    "Bug Reports": 0xff6b6b,  # Light Red
    "Ban Appeals": 0x4834d4,  # Purple Blue
}

def get_category_color(category: str) -> int:
    """Get the color associated with a ticket category"""
    return CATEGORY_COLORS.get(category, 0x7289DA)  # Default Discord blue if category not found

def get_next_ticket_number() -> str:
    """Get next sequential ticket number with thread safety"""
    global ticket_counter
    try:
        with ticket_counter_lock:
            current_tickets = list(tickets.keys())
            if current_tickets:
                # Convert existing ticket numbers to integers and find the maximum
                try:
                    max_ticket = max(int(num) for num in current_tickets if num.isdigit())
                    ticket_counter = max(max_ticket + 1, ticket_counter)
                except ValueError:
                    # If no valid numeric tickets exist, use current counter
                    pass
            
            ticket_counter += 1
            new_ticket_number = str(ticket_counter)
            log_operation("GENERATE_TICKET_NUMBER", {"new_number": new_ticket_number})
            return new_ticket_number
    except Exception as e:
        logger.error(f"Error generating ticket number: {e}")
        fallback = str(random.randint(90000, 99999))
        log_operation("GENERATE_TICKET_NUMBER_FALLBACK", {"number": fallback, "error": str(e)})
        return fallback

def has_open_ticket(user_id: str) -> bool:
    """Check if a user has any open tickets"""
    try:
        for ticket_info in tickets.values():
            if ticket_info.get('user_id') == user_id and ticket_info.get('status') == 'open':
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking open tickets: {e}")
        return False

def get_user_ticket_channel(user_id: str) -> Optional[str]:
    """Get the channel ID of user's open ticket if exists"""
    try:
        for ticket_info in tickets.values():
            if ticket_info.get('user_id') == user_id and ticket_info.get('status') == 'open':
                return ticket_info.get('channel_id')
        return None
    except Exception as e:
        logger.error(f"Error getting user ticket channel: {e}")
        return None

def create_ticket(ticket_number: str, user_id: str, channel_id: str, category: str, details: Optional[str] = None, guild_id: Optional[int] = None) -> bool:
    """Create a new ticket entry in storage"""
    try:
        if not validate_ticket_input(ticket_number, user_id, channel_id, category):
            return False

        ticket_data = {
            "ticket_number": ticket_number,
            "user_id": user_id,
            "channel_id": channel_id,
            "category": category,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "details": details or "",
            "guild_id": guild_id,
            "claimed_by": "Unclaimed",
            "closed_by": None,
            "close_reason": None,
            # Timing fields
            "created_timestamp": datetime.now(timezone.utc).timestamp(),
            "first_response_time": None,
            "first_response_timestamp": None,
            "claimed_time": None,
            "claimed_timestamp": None,
            "resolution_time": None,
            "resolution_timestamp": None,
            "response_duration": None,
            "resolution_duration": None
        }
        tickets[ticket_number] = ticket_data
        log_operation("CREATE_TICKET", {
            "ticket_number": ticket_number,
            "user_id": user_id,
            "category": category,
            "guild_id": guild_id
        })
        return True
    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        return False

def claim_ticket(ticket_number: str, claimer: str) -> bool:
    """Claim or unclaim a ticket"""
    try:
        if ticket_number not in tickets:
            logger.warning(f"Attempted to claim non-existent ticket: {ticket_number}")
            return False

        current_time = datetime.now(timezone.utc)
        
        if claimer == "Unclaimed":
            # Unclaiming the ticket
            tickets[ticket_number].update({
                "claimed_by": "Unclaimed",
                "claimed_time": None,
                "claimed_timestamp": None
            })
        else:
            # Claiming the ticket
            tickets[ticket_number].update({
                "claimed_by": claimer,
                "claimed_time": current_time.isoformat(),
                "claimed_timestamp": current_time.timestamp()
            })
        
        log_operation("CLAIM_TICKET", {
            "ticket_number": ticket_number,
            "claimer": claimer,
            "action": "unclaim" if claimer == "Unclaimed" else "claim"
        })
        return True
    except Exception as e:
        logger.error(f"Error claiming ticket: {e}")
        return False

def get_ticket_claimed_by(ticket_number: str) -> str:
    """Get who claimed a ticket"""
    try:
        ticket = tickets.get(ticket_number)
        if ticket:
            return ticket.get('claimed_by', 'Unclaimed')
        return 'Unclaimed'
    except Exception as e:
        logger.error(f"Error getting ticket claimer: {e}")
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

def store_ticket_log(ticket_number: str, messages: list, creator_id: str, category: str, 
                    claimed_by: Optional[str] = None, closed_by: Optional[str] = None, 
                    details: Optional[str] = None, guild_id: Optional[int] = None, 
                    close_reason: Optional[str] = None) -> bool:
    """Store ticket log information"""
    try:
        with ticket_logs_lock:
            logger.info(f"Storing ticket log for {ticket_number}")
            
            # Process messages to make them JSON serializable
            processed_messages = []
            for msg in messages:
                try:
                    # Extract ticket information from embed if available
                    ticket_info = {}
                    if msg.embeds:
                        embed = msg.embeds[0]
                        for field in embed.fields:
                            if "Ticket Information" in field.name:
                                # Parse ticket information from the field
                                info_text = field.value
                                if "Ticket #:" in info_text:
                                    ticket_info['number'] = info_text.split("Ticket #:")[1].split("\n")[0].strip()
                                if "Category:" in info_text:
                                    ticket_info['category'] = info_text.split("Category:")[1].split("\n")[0].strip()
                                if "Status:" in info_text:
                                    ticket_info['status'] = info_text.split("Status:")[1].strip()
                                break

                    processed_msg = {
                        "id": str(msg.id),
                        "content": msg.content,
                        "author_id": str(msg.author.id),
                        "author_name": msg.author.display_name,
                        "timestamp": msg.created_at.isoformat(),
                        "attachments": [{"url": att.url, "filename": att.filename} for att in msg.attachments],
                        "embeds": [{
                            "title": e.title,
                            "description": e.description,
                            "fields": [{"name": f.name, "value": f.value} for f in e.fields],
                            "ticket_info": ticket_info
                        } for e in msg.embeds],
                        "is_bot": msg.author.bot
                    }
                    processed_messages.append(processed_msg)
                except Exception as msg_e:
                    logger.warning(f"Error processing message {msg.id}: {msg_e}")
                    continue
            
            # Get ticket data for additional info
            ticket_data = tickets.get(ticket_number, {})
            
            # Create log entry
            log_entry = {
                "ticket_number": ticket_number,
                "creator_id": creator_id,
                "category": category,
                "claimed_by": claimed_by,
                 "closed_by": closed_by,
                "details": details,
                "guild_id": guild_id,
                "messages": processed_messages,
                "created_at": ticket_data.get("created_at", datetime.utcnow().isoformat()),
                "closed_at": datetime.utcnow().isoformat(),
                "close_reason": close_reason
            }
            
            # Store in tickets collection
            tickets[ticket_number] = log_entry
            
            logger.info(f"Successfully stored ticket log for {ticket_number}")
            return True
            
    except Exception as e:
        logger.error(f"Error storing ticket log: {e}")
        return False

def get_ticket_log(ticket_number: str) -> Optional[Dict[str, Any]]:
    """Get ticket log information"""
    try:
        with ticket_logs_lock:
            # Check if ticket exists first in logs
            if ticket_number in ticket_logs:
                log = ticket_logs[ticket_number]
                log_operation("GET_TICKET_LOG", {"ticket_number": ticket_number, "source": "logs"})
                return log
            
            # If not in logs, try to get basic ticket data from tickets dictionary
            if ticket_number in tickets:
                ticket_data = tickets[ticket_number]
                log_operation("GET_TICKET_LOG", {"ticket_number": ticket_number, "source": "basic_ticket"})
                # Create a basic log entry from ticket data
                return {
                    "ticket_number": ticket_number,
                    "creator_id": ticket_data.get("user_id"),
                    "creator_name": f"User_{ticket_data.get('user_id', 'Unknown')}",
                    "category": ticket_data.get("category"),
                    "details": ticket_data.get("details"),
                    "created_at": ticket_data.get("created_at"),
                    "guild_id": ticket_data.get("guild_id"),
                    "close_reason": ticket_data.get("close_reason", "Completed"),
                    "claimed_by": ticket_data.get("claimed_by", "Unclaimed"),
                    "closed_by": ticket_data.get("closed_by"),
                    "messages": [],  # Empty message list since we don't have the messages from logs
                    # Include timing data
                    "created_timestamp": ticket_data.get("created_timestamp"),
                    "first_response_time": ticket_data.get("first_response_time"),
                    "first_response_timestamp": ticket_data.get("first_response_timestamp"),
                    "claimed_time": ticket_data.get("claimed_time"),
                    "claimed_timestamp": ticket_data.get("claimed_timestamp"),
                    "resolution_time": ticket_data.get("resolution_time"),
                    "resolution_timestamp": ticket_data.get("resolution_timestamp"),
                    "response_duration": ticket_data.get("response_duration"),
                    "resolution_duration": ticket_data.get("resolution_duration")
                }
            
            log_operation("GET_TICKET_LOG", {"ticket_number": ticket_number, "source": "not_found"})
            return None
    except Exception as e:
        logger.error(f"Error retrieving ticket log: {e}")
        return None

def get_ticket(ticket_number: str) -> Optional[Dict[str, Any]]:
    """Get basic ticket information"""
    try:
        return tickets.get(ticket_number)
    except Exception as e:
        logger.error(f"Error getting ticket: {e}")
        return None

def close_ticket(ticket_number: str, close_reason: Optional[str] = None) -> bool:
    """Mark a ticket as closed"""
    try:
        if ticket_number not in tickets:
            logger.warning(f"Attempted to close non-existent ticket: {ticket_number}")
            return False

        close_time = datetime.now(timezone.utc)
        
        # Update ticket status
        tickets[ticket_number].update({
            "status": "closed",
            "closed_at": close_time.isoformat(),
            "close_reason": close_reason or "Completed"
        })
        
        # Also update the ticket log if it exists
        if ticket_number in ticket_logs:
            with ticket_logs_lock:
                ticket_logs[ticket_number]["closed_at"] = close_time.isoformat()
                ticket_logs[ticket_number]["close_reason"] = close_reason or "Completed"
        
        log_operation("CLOSE_TICKET", {
            "ticket_number": ticket_number,
            "close_reason": close_reason or "Completed"
        })
        return True
    except Exception as e:
        logger.error(f"Error closing ticket: {e}")
        return False

def update_ticket_times(ticket_number: str, event_type: str, user_id: str = None) -> bool:
    """Update ticket timing information with high precision"""
    try:
        if ticket_number not in tickets:
            logger.warning(f"Attempted to update times for non-existent ticket: {ticket_number}")
            return False

        current_time = datetime.now(timezone.utc)
        timestamp = current_time.timestamp()
        
        # Update ticket times
        if event_type == "created":
            tickets[ticket_number].update({
                "created_at": current_time.isoformat(),
                "created_timestamp": timestamp,
                "creator_id": user_id
            })
        elif event_type == "claimed":
            tickets[ticket_number].update({
                "claimed_time": current_time.isoformat(),
                "claimed_timestamp": timestamp,
                "claimer_id": user_id
            })
        elif event_type == "first_response":
            if not tickets[ticket_number].get("first_response_time"):
                created_timestamp = tickets[ticket_number].get("created_timestamp")
                if created_timestamp:
                    response_time = timestamp - created_timestamp
                    
                    tickets[ticket_number].update({
                        "first_response_time": current_time.isoformat(),
                        "first_response_timestamp": timestamp,
                        "response_duration": response_time,
                        "responder_id": user_id
                    })
        elif event_type == "resolved":
            if not tickets[ticket_number].get("resolution_time"):
                created_timestamp = tickets[ticket_number].get("created_timestamp")
                if created_timestamp:
                    resolution_time = timestamp - created_timestamp
                    
                    tickets[ticket_number].update({
                        "resolution_time": current_time.isoformat(),
                        "resolution_timestamp": timestamp,
                        "resolution_duration": resolution_time,
                        "resolver_id": user_id
                    })
        
        # Also update the ticket log if it exists
        if ticket_number in ticket_logs:
            with ticket_logs_lock:
                ticket_log = ticket_logs[ticket_number]
                if event_type == "created":
                    ticket_log.update({
                        "created_at": current_time.isoformat(),
                        "created_timestamp": timestamp,
                        "creator_id": user_id
                    })
                elif event_type == "claimed":
                    ticket_log.update({
                        "claimed_time": current_time.isoformat(),
                        "claimed_timestamp": timestamp,
                        "claimer_id": user_id
                    })
                elif event_type == "first_response":
                    if not ticket_log.get("first_response_time"):
                        created_timestamp = ticket_log.get("created_timestamp")
                        if created_timestamp:
                            response_time = timestamp - created_timestamp
                            
                            ticket_log.update({
                                "first_response_time": current_time.isoformat(),
                                "first_response_timestamp": timestamp,
                                "response_duration": response_time,
                                "responder_id": user_id
                            })
                elif event_type == "resolved":
                    if not ticket_log.get("resolution_time"):
                        created_timestamp = ticket_log.get("created_timestamp")
                        if created_timestamp:
                            resolution_time = timestamp - created_timestamp
                            
                            ticket_log.update({
                                "resolution_time": current_time.isoformat(),
                                "resolution_timestamp": timestamp,
                                "resolution_duration": resolution_time,
                                "resolver_id": user_id
                            })
        
        logger.info(f"Updated ticket {ticket_number} {event_type} time with timestamp {timestamp}")
        return True
    except Exception as e:
        logger.error(f"Error updating ticket times: {e}")
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

def get_all_tickets() -> Dict[str, Dict[str, Any]]:
    """Get all tickets"""
    try:
        return tickets.copy()
    except Exception as e:
        logger.error(f"Error getting all tickets: {e}")
        return {}

def get_tickets_by_status(status: str) -> Dict[str, Dict[str, Any]]:
    """Get tickets by status"""
    try:
        return {k: v for k, v in tickets.items() if v.get('status') == status}
    except Exception as e:
        logger.error(f"Error getting tickets by status: {e}")
        return {}

def get_tickets_by_user(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Get all tickets for a specific user"""
    try:
        return {k: v for k, v in tickets.items() if v.get('user_id') == user_id}
    except Exception as e:
        logger.error(f"Error getting tickets by user: {e}")
        return {}

def get_tickets_by_category(category: str) -> Dict[str, Dict[str, Any]]:
    """Get tickets by category"""
    try:
        return {k: v for k, v in tickets.items() if v.get('category') == category}
    except Exception as e:
        logger.error(f"Error getting tickets by category: {e}")
        return {}

def update_ticket(ticket_number: str, updates: Dict[str, Any]) -> bool:
    """Update ticket information"""
    try:
        if ticket_number not in tickets:
            logger.error(f"Ticket {ticket_number} not found for update")
            return False
        
        tickets[ticket_number].update(updates)
        log_operation("UPDATE_TICKET", {
            "ticket_number": ticket_number,
            "updates": list(updates.keys())
        })
        return True
    except Exception as e:
        logger.error(f"Error updating ticket: {e}")
        return False

def get_ticket_statistics() -> Dict[str, Any]:
    """Get ticket statistics"""
    try:
        stats = {
            "total_tickets": len(tickets),
            "open_tickets": len([t for t in tickets.values() if t.get('status') == 'open']),
            "closed_tickets": len([t for t in tickets.values() if t.get('status') == 'closed']),
            "claimed_tickets": len([t for t in tickets.values() if t.get('claimed_by') != 'Unclaimed']),
            "categories": {},
            "total_feedback": len(feedback_storage),
            "average_rating": 0.0
        }
        
        # Category statistics
        for ticket in tickets.values():
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
        if feedback_storage:
            ratings = [f.get('rating', 0) for f in feedback_storage.values() if f.get('rating')]
            if ratings:
                stats['average_rating'] = sum(ratings) / len(ratings)
        
        return stats
    except Exception as e:
        logger.error(f"Error getting ticket statistics: {e}")
        return {}

def export_data() -> Dict[str, Any]:
    """Export all data for backup purposes"""
    try:
        return {
            "tickets": tickets.copy(),
            "feedback": feedback_storage.copy(),
            "ticket_logs": ticket_logs.copy(),
            "ticket_counter": ticket_counter,
            "export_timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return {}

def import_data(data: Dict[str, Any]) -> bool:
    """Import data from backup"""
    try:
        global tickets, feedback_storage, ticket_logs, ticket_counter
        
        if 'tickets' in data:
            tickets.update(data['tickets'])
        if 'feedback' in data:
            feedback_storage.update(data['feedback'])
        if 'ticket_logs' in data:
            ticket_logs.update(data['ticket_logs'])
        if 'ticket_counter' in data:
            ticket_counter = max(ticket_counter, data['ticket_counter'])
        
        log_operation("IMPORT_DATA", {
            "tickets_imported": len(data.get('tickets', {})),
            "feedback_imported": len(data.get('feedback', {}))
        })
        return True
    except Exception as e:
        logger.error(f"Error importing data: {e}")
        return False

def search_tickets(query: str, search_in: List[str] = None) -> Dict[str, Dict[str, Any]]:
    """Search tickets by query"""
    try:
        if search_in is None:
            search_in = ['category', 'details', 'user_id', 'claimed_by']
        
        results = {}
        query_lower = query.lower()
        
        for ticket_number, ticket_data in tickets.items():
            for field in search_in:
                field_value = str(ticket_data.get(field, '')).lower()
                if query_lower in field_value:
                    results[ticket_number] = ticket_data
                    break
        
        log_operation("SEARCH_TICKETS", {
            "query": query,
            "results": len(results)
        })
        return results
    except Exception as e:
        logger.error(f"Error searching tickets: {e}")
        return {}

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