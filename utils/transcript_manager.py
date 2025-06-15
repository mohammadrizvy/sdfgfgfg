import discord
import io
import aiohttp
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
import json
import os

logger = logging.getLogger('discord')

class TranscriptManager:
    def __init__(self, bot):
        self.bot = bot
        self.transcript_dir = "transcripts"
        os.makedirs(self.transcript_dir, exist_ok=True)
        logger.info("TranscriptManager initialized")

    def get_sample_transcript(self, ticket_number: str) -> str:
        """Return a sample transcript to demonstrate the format"""
        content = io.StringIO()
        
        # Write header
        content.write("=" * 70 + "\n")
        content.write(f"{'TICKET TRANSCRIPT #' + ticket_number:^70}\n")
        content.write("=" * 70 + "\n\n")
        
        # Write ticket information
        content.write("Ticket Information:\n")
        content.write(f"├─ Ticket Number: #{ticket_number}\n")
        content.write(f"├─ Category: Slayer Carry\n")
        content.write(f"├─ Creator: JohnDoe\n")
        content.write(f"├─ Participants: JohnDoe, StaffMember\n")
        content.write(f"├─ Duration: 0:45:23\n")
        content.write(f"├─ Claimed by: StaffMember\n")
        content.write(f"├─ Total Messages: 15\n")
        content.write(f"└─ Generated: 2024-03-20 15:30:45 UTC\n\n")
        
        # Write conversation log header
        content.write("=" * 70 + "\n")
        content.write(f"{'CONVERSATION LOG':^70}\n")
        content.write("=" * 70 + "\n\n")
        
        # Write sample messages
        content.write("[2024-03-20 14:45:22] JohnDoe: Hi, I need help with my slayer task\n")
        content.write("[2024-03-20 14:45:30] StaffMember: Hello! I'll help you with that. What's your task?\n")
        content.write("[2024-03-20 14:45:45] JohnDoe: I need to kill 150 abyssal demons\n")
        content.write("[2024-03-20 14:46:00] StaffMember: I can help you with that. Do you have the required combat level?\n")
        content.write("[2024-03-20 14:46:15] JohnDoe: Yes, I'm level 85 combat\n")
        content.write("[2024-03-20 14:46:30] StaffMember: Perfect! Let's get started. I'll meet you at the abyssal demons\n")
        content.write("[2024-03-20 14:47:00] JohnDoe: Great, I'm ready\n")
        content.write("[2024-03-20 14:47:15] StaffMember: I'm on my way. Please wait at the entrance\n")
        content.write("[2024-03-20 14:48:00] JohnDoe: I'm here\n")
        content.write("[2024-03-20 14:48:15] StaffMember: I see you. Let's begin the task\n")
        content.write("[2024-03-20 15:20:00] JohnDoe: That was quick! Thank you for the help\n")
        content.write("[2024-03-20 15:20:15] StaffMember: You're welcome! Is there anything else you need?\n")
        content.write("[2024-03-20 15:20:30] JohnDoe: No, that's all. Thanks again!\n")
        content.write("[2024-03-20 15:20:45] StaffMember: Have a great day! The ticket will be closed now\n")
        
        # Add feedback section
        content.write("\n" + "=" * 70 + "\n")
        content.write(f"{'CUSTOMER FEEDBACK':^70}\n")
        content.write("=" * 70 + "\n\n")
        content.write("Rating: ⭐⭐⭐⭐⭐ (5/5)\n")
        content.write("Submitted: 2024-03-20 15:25:00 UTC\n\n")
        content.write("Feedback:\n")
        content.write("The staff member was very helpful and efficient. Completed my slayer task quickly and professionally.\n\n")
        content.write("Suggestions for Improvement:\n")
        content.write("None, everything was perfect!\n")
        
        content.write("\n" + "=" * 70 + "\n")
        content.write(f"{'END OF TRANSCRIPT':^70}\n")
        content.write("=" * 70 + "\n")
        
        return content.getvalue()

    def generate_transcript_file(self, ticket_number: str, messages: List[discord.Message], 
                               ticket_data: Dict[str, Any]) -> str:
        print(f"[DEBUG] TranscriptManager: Generating transcript for ticket {ticket_number}")
        # Format transcript as plain text
        transcript = self._format_transcript(ticket_number, messages, ticket_data)
        filename = f"transcript_{ticket_number}_{uuid.uuid4().hex[:8]}.txt"
        filepath = os.path.join(self.transcript_dir, filename)
        print(f"[DEBUG] TranscriptManager: Saving transcript to {filepath}")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(transcript)
            print(f"[DEBUG] TranscriptManager: Successfully wrote transcript to {filepath}")
        except IOError as e:
            logger.error(f"[TranscriptManager Error] Failed to write transcript file {filepath}: {e}", exc_info=True)
            print(f"[DEBUG] TranscriptManager: Failed to write transcript file {filepath}: {e}")
            raise # Re-raise to be caught by calling function
        return filepath  # Return the local file path

    def update_transcript_with_feedback(self, ticket_number: str, feedback_data: Dict[str, Any]) -> Optional[str]:
        """Update transcript with feedback and return a new Tenor-style URL"""
        try:
            # Generate a new unique identifier for the updated transcript
            transcript_id = str(uuid.uuid4())
            
            # Get the original transcript
            original_transcript = self._get_original_transcript(ticket_number)
            if not original_transcript:
                logger.error(f"Could not find original transcript for ticket {ticket_number}")
                return None
            
            # Add feedback section
            updated_transcript = self._add_feedback_section(original_transcript, feedback_data)
            
            # Save the updated transcript
            filename = f"transcript_{ticket_number}_{transcript_id}_with_feedback.txt"
            filepath = os.path.join(self.transcript_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_transcript)
            
            # Generate and return the new Tenor-style URL
            transcript_url = f"https://tenor.com/view/ticket-{ticket_number}-transcript-{transcript_id}"
            
            logger.info(f"Generated updated transcript URL: {transcript_url}")
            return transcript_url
            
        except Exception as e:
            logger.error(f"Error updating transcript with feedback: {e}")
            return None

    def _format_transcript(self, ticket_number: str, messages: List[discord.Message], 
                          ticket_data: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"=== Ticket Transcript #{ticket_number} ===")
        lines.append(f"Category: {ticket_data.get('category', 'Unknown')}")
        lines.append(f"Created by: {ticket_data.get('creator_id', 'Unknown')}")
        lines.append(f"Created at: {ticket_data.get('created_at', 'Unknown')}")
        lines.append(f"Total Messages: {len(messages)}")
        lines.append(f"Generated at: {datetime.utcnow().isoformat()}")
        lines.append("=" * 50)
        lines.append("Conversation Log:")
        for msg in messages:
            timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
            author = getattr(msg.author, 'display_name', str(msg.author))
            content = msg.content or "[embed/attachment]"
            lines.append(f"[{timestamp}] {author}: {content}")
        return "\n".join(lines)

    def _get_original_transcript(self, ticket_number: str) -> Optional[str]:
        """Get the original transcript content"""
        try:
            # Find the most recent transcript file for this ticket
            transcript_files = [f for f in os.listdir(self.transcript_dir) 
                              if f.startswith(f"transcript_{ticket_number}_")]
            
            if not transcript_files:
                return None
            
            # Get the most recent file
            latest_file = max(transcript_files, key=lambda x: os.path.getctime(os.path.join(self.transcript_dir, x)))
            
            # Read the file
            with open(os.path.join(self.transcript_dir, latest_file), 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error getting original transcript: {e}")
            return None

    def _add_feedback_section(self, transcript: str, feedback_data: Dict[str, Any]) -> str:
        """Add feedback section to the transcript"""
        try:
            feedback_section = [
                "\n" + "=" * 50,
                "Customer Feedback",
                "=" * 50,
                f"\nRating: {'⭐' * feedback_data.get('rating', 0)}",
                f"Submitted at: {feedback_data.get('submitted_at', datetime.now().isoformat())}",
                f"\nFeedback:",
                feedback_data.get('feedback', 'No feedback provided'),
                f"\nSuggestions for Improvement:",
                feedback_data.get('suggestions', 'No suggestions provided')
            ]
            
            return transcript + "\n".join(feedback_section)
            
        except Exception as e:
            logger.error(f"Error adding feedback section: {e}")
            return transcript 