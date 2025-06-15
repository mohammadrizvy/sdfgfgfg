import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'carry_service')

# Collection Names
COLLECTIONS = {
    'tickets': 'tickets',
    'ticket_messages': 'ticket_messages',
    'feedback': 'feedback',
    'staff_roles': 'staff_roles',
    'user_tickets': 'user_tickets',
    'ticket_logs': 'ticket_logs',
    'bot_config': 'bot_config',
    'archives': 'ticket_archives',
    'analytics': 'ticket_analytics',
    'transcripts': 'ticket_transcripts',
    'feedback_categories': 'feedback_categories'
}

# Ticket Configuration
TICKET_START_NUMBER = 10000
TICKET_CATEGORIES = [
    "Slayer Carry",
    "Normal Dungeon Carry",
    "Master Dungeon Carry"
]

# Ticket Priority Levels
PRIORITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "URGENT"]

# Feedback Categories
FEEDBACK_CATEGORIES = {
    "service_quality": {
        "name": "Service Quality",
        "description": "Rating of the overall service quality",
        "options": ["Poor", "Fair", "Good", "Excellent"]
    },
    "carrier_behavior": {
        "name": "Carrier Behavior",
        "description": "Rating of the carrier's behavior and professionalism",
        "options": ["Poor", "Fair", "Good", "Excellent"]
    },
    "communication": {
        "name": "Communication",
        "description": "Rating of the communication during the service",
        "options": ["Poor", "Fair", "Good", "Excellent"]
    },
    "value_for_money": {
        "name": "Value for Money",
        "description": "Rating of the value for money",
        "options": ["Poor", "Fair", "Good", "Excellent"]
    }
}

# Transcript Categories
TRANSCRIPT_CATEGORIES = {
    "ticket_info": {
        "name": "Ticket Information",
        "fields": ["ticket_number", "user_id", "category", "status", "created_at", "closed_at"]
    },
    "messages": {
        "name": "Ticket Messages",
        "fields": ["timestamp", "author_id", "content", "attachments"]
    },
    "actions": {
        "name": "Ticket Actions",
        "fields": ["action_type", "performed_by", "timestamp", "details"]
    },
    "feedback": {
        "name": "Ticket Feedback",
        "fields": ["rating", "categories", "comments", "submitted_at"]
    }
}
