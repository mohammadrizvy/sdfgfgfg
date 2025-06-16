import discord
import io
import aiohttp
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
import json
import os
from .html_transcript_generator import DiscordTranscriptGenerator

logger = logging.getLogger('discord')

class TranscriptManager:
    def __init__(self, bot):
        self.bot = bot
        self.transcript_dir = "transcripts"
        self.html_generator = DiscordTranscriptGenerator(bot)
        os.makedirs(self.transcript_dir, exist_ok=True)
        logger.info("Enhanced TranscriptManager initialized")

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

    async def generate_html_transcript(self, ticket_number: str, messages: List[discord.Message], 
                                     ticket_data: Dict[str, Any]) -> Optional[str]:
        """Generate a beautiful HTML transcript using the new generator"""
        try:
            return await self.html_generator.generate_html_transcript(ticket_number, messages, ticket_data)
        except Exception as e:
            logger.error(f"Error generating HTML transcript: {e}")
            return None

    def generate_transcript_file(self, ticket_number: str, messages: List[discord.Message], 
                               ticket_data: Dict[str, Any]) -> str:
        """Generate a traditional text transcript file (fallback)"""
        try:
            transcript = self._format_transcript(ticket_number, messages, ticket_data)
            filename = f"transcript_{ticket_number}_{uuid.uuid4().hex[:8]}.txt"
            filepath = os.path.join(self.transcript_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(transcript)
            
            logger.info(f"Generated text transcript: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error generating text transcript: {e}")
            return None

    async def generate_comprehensive_transcript(self, ticket_number: str, messages: List[discord.Message], 
                                              ticket_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate both HTML and text transcripts"""
        results = {}
        
        # Generate HTML transcript
        html_url = await self.generate_html_transcript(ticket_number, messages, ticket_data)
        if html_url:
            results['html_url'] = html_url
        
        # Generate text transcript (fallback)
        text_file = self.generate_transcript_file(ticket_number, messages, ticket_data)
        if text_file:
            results['text_file'] = text_file
        
        return results

    def update_transcript_with_feedback(self, ticket_number: str, feedback_data: Dict[str, Any]) -> Optional[str]:
        """Update transcript with feedback and return a new URL"""
        try:
            # Generate a new unique identifier for the updated transcript
            transcript_id = str(uuid.uuid4())
            
            # For now, return a placeholder URL - in production, implement feedback integration
            transcript_url = f"https://your-domain.com/transcripts/ticket_{ticket_number}_{transcript_id}_with_feedback.html"
            
            logger.info(f"Generated updated transcript URL with feedback: {transcript_url}")
            return transcript_url
            
        except Exception as e:
            logger.error(f"Error updating transcript with feedback: {e}")
            return None

    def _format_transcript(self, ticket_number: str, messages: List[discord.Message], 
                          ticket_data: Dict[str, Any]) -> str:
        """Format traditional text transcript"""
        lines = []
        lines.append(f"=== Ticket Transcript #{ticket_number} ===")
        lines.append(f"Category: {ticket_data.get('category', 'Unknown')}")
        lines.append(f"Created by: {ticket_data.get('creator_id', 'Unknown')}")
        lines.append(f"Claimed by: {ticket_data.get('claimed_by', 'Unclaimed')}")
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
        
        lines.append("\n" + "=" * 50)
        lines.append("END OF TRANSCRIPT")
        lines.append("=" * 50)
        
        return "\n".join(lines)

    async def store_transcript_metadata(self, ticket_number: str, transcript_data: Dict[str, Any]) -> bool:
        """Store transcript metadata in database"""
        try:
            # In a real implementation, store this in your database
            metadata = {
                "ticket_number": ticket_number,
                "generated_at": datetime.utcnow().isoformat(),
                "html_url": transcript_data.get('html_url'),
                "text_file": transcript_data.get('text_file'),
                "message_count": transcript_data.get('message_count', 0),
                "participants": transcript_data.get('participants', [])
            }
            
            # Save metadata to file for now (replace with database storage)
            metadata_file = os.path.join(self.transcript_dir, f"metadata_{ticket_number}.json")
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Stored transcript metadata for ticket {ticket_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing transcript metadata: {e}")
            return False

    async def get_transcript_stats(self) -> Dict[str, Any]:
        """Get statistics about generated transcripts"""
        try:
            transcript_files = [f for f in os.listdir(self.transcript_dir) if f.startswith('transcript_')]
            html_files = [f for f in os.listdir(self.html_generator.transcript_dir) if f.endswith('.html')]
            
            return {
                "total_text_transcripts": len(transcript_files),
                "total_html_transcripts": len(html_files),
                "storage_used": self._calculate_storage_used(),
                "last_generated": self._get_last_generation_time()
            }
        except Exception as e:
            logger.error(f"Error getting transcript stats: {e}")
            return {}

    def _calculate_storage_used(self) -> str:
        """Calculate total storage used by transcripts"""
        try:
            total_size = 0
            for root, dirs, files in os.walk(self.transcript_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
            
            for root, dirs, files in os.walk(self.html_generator.transcript_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
            
            # Convert to human readable format
            for unit in ['B', 'KB', 'MB', 'GB']:
                if total_size < 1024.0:
                    return f"{total_size:.1f} {unit}"
                total_size /= 1024.0
            return f"{total_size:.1f} TB"
            
        except Exception as e:
            logger.error(f"Error calculating storage: {e}")
            return "Unknown"

    def _get_last_generation_time(self) -> Optional[str]:
        """Get the time of the last transcript generation"""
        try:
            all_files = []
            
            # Check text transcripts
            for file in os.listdir(self.transcript_dir):
                if file.startswith('transcript_'):
                    file_path = os.path.join(self.transcript_dir, file)
                    all_files.append(file_path)
            
            # Check HTML transcripts
            for file in os.listdir(self.html_generator.transcript_dir):
                if file.endswith('.html'):
                    file_path = os.path.join(self.html_generator.transcript_dir, file)
                    all_files.append(file_path)
            
            if not all_files:
                return None
            
            # Get the most recent file
            latest_file = max(all_files, key=os.path.getctime)
            timestamp = os.path.getctime(latest_file)
            return datetime.fromtimestamp(timestamp).isoformat()
            
        except Exception as e:
            logger.error(f"Error getting last generation time: {e}")
            return None

    async def cleanup_old_transcripts(self, max_age_days: int = 30) -> int:
        """Clean up old transcript files"""
        try:
            import time
            
            current_time = time.time()
            cutoff_time = current_time - (max_age_days * 24 * 60 * 60)
            
            deleted_count = 0
            
            # Clean text transcripts
            for file in os.listdir(self.transcript_dir):
                file_path = os.path.join(self.transcript_dir, file)
                if os.path.getctime(file_path) < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
            
            # Clean HTML transcripts
            for file in os.listdir(self.html_generator.transcript_dir):
                file_path = os.path.join(self.html_generator.transcript_dir, file)
                if os.path.getctime(file_path) < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old transcript files")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up transcripts: {e}")
            return 0 