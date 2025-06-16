import discord
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import asyncio
import aiohttp
from pathlib import Path
import re
import html

logger = logging.getLogger('discord')

class DiscordTranscriptGenerator:
    def __init__(self, bot):
        self.bot = bot
        self.transcript_dir = Path("web_transcripts")
        self.transcript_dir.mkdir(exist_ok=True)
        # The base_url will be set by the web server
        self.base_url = None  # This will be updated when generating transcripts
        
    async def generate_html_transcript(self, ticket_number: str, messages: List[discord.Message], 
                                     ticket_data: Dict[str, Any]) -> str:
        """Generate a beautiful HTML transcript that looks like Discord"""
        try:
            # Generate unique ID for this transcript
            transcript_id = str(uuid.uuid4())
            
            # Collect user data and message data
            participants = {}
            formatted_messages = []
            
            for message in messages:
                # Collect participant data
                if message.author.id not in participants:
                    participants[message.author.id] = await self._get_user_data(message.author)
                
                # Format message data
                formatted_message = await self._format_message(message)
                formatted_messages.append(formatted_message)
            
            # Generate HTML content
            html_content = await self._generate_html_content(
                ticket_number, ticket_data, participants, formatted_messages
            )
            
            # Save HTML file with the transcript ID as the filename
            filename = f"ticket_{transcript_id}.html"
            file_path = self.transcript_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Generate secure URL with access token
            transcript_url = self.bot.web_server.get_transcript_url(transcript_id, ticket_number)
            
            logger.info(f"Generated HTML transcript: {transcript_url}")
            return transcript_url
            
        except Exception as e:
            logger.error(f"Error generating HTML transcript: {e}")
            return None

    async def _get_user_data(self, user: discord.Member) -> Dict[str, Any]:
        """Extract user data for the transcript"""
        try:
            # Get user avatar URL
            avatar_url = user.display_avatar.url if user.display_avatar else user.default_avatar.url
            
            # Get user roles and colors
            top_role = user.top_role if hasattr(user, 'top_role') and user.top_role.name != '@everyone' else None
            role_color = str(top_role.color) if top_role and top_role.color != discord.Color.default() else '#ffffff'
            
            # Check if user is bot
            is_bot = user.bot
            
            # Get user status
            status = 'online'
            if hasattr(user, 'status'):
                status = str(user.status)
            
            return {
                'id': str(user.id),
                'username': user.name,
                'display_name': user.display_name if hasattr(user, 'display_name') else user.name,
                'discriminator': user.discriminator if hasattr(user, 'discriminator') else '0000',
                'avatar_url': avatar_url,
                'role_color': role_color,
                'is_bot': is_bot,
                'status': status,
                'roles': [role.name for role in user.roles if role.name != '@everyone'] if hasattr(user, 'roles') else []
            }
        except Exception as e:
            logger.error(f"Error getting user data: {e}")
            return {
                'id': str(user.id),
                'username': str(user),
                'display_name': str(user),
                'discriminator': '0000',
                'avatar_url': user.default_avatar.url if hasattr(user, 'default_avatar') else '',
                'role_color': '#ffffff',
                'is_bot': False,
                'status': 'offline',
                'roles': []
            }

    async def _format_message(self, message: discord.Message) -> Dict[str, Any]:
        """Format a Discord message for HTML display"""
        try:
            # Format content
            content = self._format_message_content(message.content)
            
            # Get attachments
            attachments = []
            for attachment in message.attachments:
                attachments.append({
                    'url': attachment.url,
                    'filename': attachment.filename,
                    'size': attachment.size,
                    'is_image': any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'])
                })
            
            # Get embeds
            embeds = []
            for embed in message.embeds:
                embeds.append(await self._format_embed(embed))
            
            # Get reactions
            reactions = []
            for reaction in message.reactions:
                reactions.append({
                    'emoji': str(reaction.emoji),
                    'count': reaction.count
                })
            
            return {
                'id': str(message.id),
                'author_id': str(message.author.id),
                'content': content,
                'timestamp': message.created_at.isoformat(),
                'edited_timestamp': message.edited_at.isoformat() if message.edited_at else None,
                'attachments': attachments,
                'embeds': embeds,
                'reactions': reactions,
                'is_reply': message.reference is not None,
                'reply_to': str(message.reference.message_id) if message.reference else None
            }
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            return {
                'id': str(message.id),
                'author_id': str(message.author.id),
                'content': html.escape(message.content or ''),
                'timestamp': message.created_at.isoformat(),
                'edited_timestamp': None,
                'attachments': [],
                'embeds': [],
                'reactions': [],
                'is_reply': False,
                'reply_to': None
            }

    def _format_message_content(self, content: str) -> str:
        """Format message content with Discord markdown and mentions"""
        if not content:
            return ''
        
        # Escape HTML first
        content = html.escape(content)
        
        # Format Discord markdown
        # Bold
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        # Italic
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        # Underline
        content = re.sub(r'__(.*?)__', r'<u>\1</u>', content)
        # Strikethrough
        content = re.sub(r'~~(.*?)~~', r'<del>\1</del>', content)
        # Code blocks
        content = re.sub(r'```([^`]+)```', r'<pre><code>\1</code></pre>', content, flags=re.DOTALL)
        # Inline code
        content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
        # Convert newlines to breaks
        content = content.replace('\n', '<br>')
        
        return content

    async def _format_embed(self, embed: discord.Embed) -> Dict[str, Any]:
        """Format Discord embed for HTML display"""
        try:
            return {
                'title': embed.title or '',
                'description': embed.description or '',
                'color': str(embed.color) if embed.color else '#000000',
                'fields': [{'name': field.name, 'value': field.value, 'inline': field.inline} for field in embed.fields],
                'footer': {'text': embed.footer.text, 'icon_url': embed.footer.icon_url} if embed.footer else None,
                'author': {'name': embed.author.name, 'icon_url': embed.author.icon_url} if embed.author else None,
                'thumbnail': embed.thumbnail.url if embed.thumbnail else None,
                'image': embed.image.url if embed.image else None,
                'timestamp': embed.timestamp.isoformat() if embed.timestamp else None
            }
        except Exception as e:
            logger.error(f"Error formatting embed: {e}")
            return {'title': '', 'description': '', 'color': '#000000', 'fields': []}

    async def _generate_html_content(self, ticket_number: str, ticket_data: Dict[str, Any], 
                                   participants: Dict[str, Any], messages: List[Dict[str, Any]]) -> str:
        """Generate enhanced HTML content for the transcript"""
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Ticket Transcript #{ticket_number} - FakePixel Giveaways</title>
            <link rel="icon" href="https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo" type="image/png">
            <style>{self._get_discord_css()}</style>
        </head>
        <body>
            <div class="watermark"></div>
            <div class="transcript-container">
                <div class="transcript-header">
                    <img src="https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo" alt="FakePixel Logo" class="server-logo">
                    <h1 class="transcript-title">
                        <span>🎫</span>
                        Ticket Transcript #{ticket_number}
                    </h1>
                </div>
                
                <div class="transcript-info">
                    <div class="info-item">
                        <span class="info-label">Category</span>
                        <span class="info-value">{ticket_data.get('category', 'Unknown')}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Created By</span>
                        <span class="info-value">{participants.get(ticket_data.get('creator_id', ''), {}).get('display_name', 'Unknown')}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Created At</span>
                        <span class="info-value">{self._format_timestamp(ticket_data.get('created_at', ''))}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Status</span>
                        <span class="info-value">{ticket_data.get('status', 'Closed')}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Total Messages</span>
                        <span class="info-value">{len(messages)}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Participants</span>
                        <span class="info-value">{len(participants)}</span>
                    </div>
                </div>

                <div class="messages-container">
                    {self._generate_messages_html(messages, participants)}
                </div>

                {self._generate_feedback_section(ticket_data)}

                <div class="transcript-footer">
                    <p>Generated by FakePixel Giveaways Carry Support • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
            </div>
            <script>{self._get_discord_js()}</script>
        </body>
        </html>
        """
        return html_content

    def _generate_messages_html(self, messages: List[Dict[str, Any]], participants: Dict[str, Any]) -> str:
        """Generate HTML for all messages"""
        html_parts = []
        
        for message in messages:
            author_id = message['author_id']
            author = participants.get(author_id, {})
            
            # Format timestamp
            timestamp = self._format_timestamp(message['timestamp'])
            
            # Check if edited
            edited = message['edited_timestamp'] is not None
            
            html_parts.append(f'''
            <div class="message" data-message-id="{message['id']}">
                <div class="message-left">
                    <img src="{author.get('avatar_url', '')}" alt="{author.get('username', 'Unknown')}" class="avatar">
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="username" style="color: {author.get('role_color', '#ffffff')}">{author.get('display_name', 'Unknown')}</span>
                        {'<span class="bot-tag">BOT</span>' if author.get('is_bot', False) else ''}
                        <span class="timestamp">{timestamp}</span>
                        {'<span class="edited">(edited)</span>' if edited else ''}
                    </div>
                    <div class="message-text">
                        {message['content']}
                    </div>
                    {self._generate_attachments_html(message['attachments'])}
                    {self._generate_embeds_html(message['embeds'])}
                    {self._generate_reactions_html(message['reactions'])}
                </div>
            </div>
            ''')
        
        return ''.join(html_parts)

    def _generate_attachments_html(self, attachments: List[Dict[str, Any]]) -> str:
        """Generate HTML for message attachments"""
        if not attachments:
            return ''
        
        html_parts = []
        for attachment in attachments:
            if attachment['is_image']:
                html_parts.append(f'''
                <div class="attachment image-attachment" data-url="{attachment['url']}">
                    <img src="{attachment['url']}" alt="{attachment['filename']}" class="attachment-icon">
                </div>
                ''')
            else:
                html_parts.append(f'''
                <div class="attachment file-attachment" data-url="{attachment['url']}">
                    <div class="file-info">
                        <div class="file-icon">📎</div>
                        <div class="file-details">
                            <div class="file-name">{attachment['filename']}</div>
                            <div class="file-size">{self._format_file_size(attachment['size'])}</div>
                        </div>
                        <a href="{attachment['url']}" target="_blank" class="download-btn">Download</a>
                    </div>
                </div>
                ''')
        
        return ''.join(html_parts)

    def _generate_embeds_html(self, embeds: List[Dict[str, Any]]) -> str:
        """Generate HTML for message embeds"""
        if not embeds:
            return ''
        
        html_parts = []
        for embed in embeds:
            html_parts.append(f'''
            <div class="embed" style="border-left-color: {embed['color']}">
                {f'<div class="embed-author"><img src="{embed["author"]["icon_url"]}" class="embed-author-icon"><span>{embed["author"]["name"]}</span></div>' if embed.get('author') else ''}
                {f'<div class="embed-title">{embed["title"]}</div>' if embed.get('title') else ''}
                {f'<div class="embed-description">{embed["description"]}</div>' if embed.get('description') else ''}
                {self._generate_embed_fields_html(embed.get('fields', []))}
                {f'<img src="{embed["image"]}" class="embed-image">' if embed.get('image') else ''}
                {f'<div class="embed-footer"><img src="{embed["footer"]["icon_url"]}" class="embed-footer-icon"><span>{embed["footer"]["text"]}</span></div>' if embed.get('footer') else ''}
            </div>
            ''')
        
        return ''.join(html_parts)

    def _generate_embed_fields_html(self, fields: List[Dict[str, Any]]) -> str:
        """Generate HTML for embed fields"""
        if not fields:
            return ''
        
        html_parts = ['<div class="embed-fields">']
        for field in fields:
            inline_class = 'embed-field-inline' if field.get('inline', False) else ''
            html_parts.append(f'''
            <div class="embed-field {inline_class}">
                <div class="embed-field-name">{field['name']}</div>
                <div class="embed-field-value">{field['value']}</div>
            </div>
            ''')
        html_parts.append('</div>')
        
        return ''.join(html_parts)

    def _generate_reactions_html(self, reactions: List[Dict[str, Any]]) -> str:
        """Generate HTML for message reactions"""
        if not reactions:
            return ''
        
        html_parts = ['<div class="reactions">']
        for reaction in reactions:
            html_parts.append(f'''
            <div class="reaction">
                <span class="reaction-emoji">{reaction['emoji']}</span>
                <span class="reaction-count">{reaction['count']}</span>
            </div>
            ''')
        html_parts.append('</div>')
        
        return ''.join(html_parts)

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%m/%d/%Y %I:%M %p')
        except:
            return timestamp_str

    def _format_date(self, date_str: str) -> str:
        """Format date for display"""
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %I:%M %p')
        except:
            return date_str

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size for display"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _get_discord_css(self) -> str:
        """Get enhanced CSS for Discord-like styling"""
        return """
        :root {
            --discord-dark: #36393f;
            --discord-darker: #2f3136;
            --discord-darkest: #202225;
            --discord-light: #dcddde;
            --discord-lighter: #ffffff;
            --discord-accent: #5865f2;
            --discord-green: #43b581;
            --discord-red: #f04747;
            --discord-yellow: #faa61a;
            --discord-purple: #7289da;
        }

        body {
            font-family: 'gg sans', 'Noto Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background-color: var(--discord-dark);
            color: var(--discord-light);
            line-height: 1.5;
            margin: 0;
            padding: 20px;
        }

        .transcript-container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: var(--discord-darker);
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            overflow: hidden;
        }

        .transcript-header {
            background-color: var(--discord-darkest);
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
        }

        .server-logo {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
        }

        .transcript-title {
            color: var(--discord-lighter);
            font-size: 24px;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .transcript-title::before {
            content: "";
            display: inline-block;
            width: 24px;
            height: 24px;
            background-image: url('https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo');
            background-size: contain;
            background-repeat: no-repeat;
        }

        .transcript-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 20px;
            background-color: var(--discord-darkest);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .info-item {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .info-label {
            color: var(--discord-light);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .info-value {
            color: var(--discord-lighter);
            font-size: 14px;
            font-weight: 500;
        }

        .messages-container {
            padding: 20px;
        }

        .message {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 16px;
            padding: 8px 0;
            position: relative;
        }

        .message:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }

        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
        }

        .message-content {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .message-header {
            display: flex;
            align-items: baseline;
            gap: 8px;
        }

        .username {
            color: var(--discord-lighter);
            font-weight: 500;
            font-size: 16px;
        }

        .timestamp {
            color: var(--discord-light);
            font-size: 12px;
            opacity: 0.7;
        }

        .message-text {
            color: var(--discord-light);
            font-size: 14px;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .message-text a {
            color: var(--discord-accent);
            text-decoration: none;
        }

        .message-text a:hover {
            text-decoration: underline;
        }

        .attachments {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 8px;
        }

        .attachment {
            background-color: var(--discord-darkest);
            border-radius: 4px;
            padding: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .attachment-icon {
            width: 24px;
            height: 24px;
            opacity: 0.7;
        }

        .attachment-info {
            flex: 1;
            min-width: 0;
        }

        .attachment-name {
            color: var(--discord-lighter);
            font-size: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .attachment-size {
            color: var(--discord-light);
            font-size: 12px;
            opacity: 0.7;
        }

        .embed {
            background-color: var(--discord-darkest);
            border-left: 4px solid var(--discord-accent);
            border-radius: 4px;
            padding: 10px;
            margin-top: 8px;
        }

        .embed-title {
            color: var(--discord-lighter);
            font-size: 16px;
            font-weight: 500;
            margin-bottom: 8px;
        }

        .embed-description {
            color: var(--discord-light);
            font-size: 14px;
            white-space: pre-wrap;
        }

        .embed-fields {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 8px;
        }

        .embed-field {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .embed-field-name {
            color: var(--discord-lighter);
            font-size: 14px;
            font-weight: 500;
        }

        .embed-field-value {
            color: var(--discord-light);
            font-size: 14px;
        }

        .reactions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }

        .reaction {
            background-color: var(--discord-darkest);
            border-radius: 12px;
            padding: 4px 8px;
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 12px;
            color: var(--discord-light);
        }

        .reaction-count {
            color: var(--discord-light);
            opacity: 0.7;
        }

        .transcript-footer {
            background-color: var(--discord-darkest);
            padding: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            text-align: center;
            color: var(--discord-light);
            font-size: 12px;
        }

        .feedback-section {
            background-color: var(--discord-darkest);
            padding: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            margin-top: 20px;
        }

        .feedback-title {
            color: var(--discord-lighter);
            font-size: 18px;
            margin-bottom: 16px;
        }

        .feedback-content {
            color: var(--discord-light);
            font-size: 14px;
            white-space: pre-wrap;
        }

        .rating {
            display: flex;
            gap: 4px;
            margin-bottom: 8px;
        }

        .star {
            color: var(--discord-yellow);
            font-size: 20px;
        }

        @media (max-width: 768px) {
            .transcript-container {
                border-radius: 0;
            }

            .message {
                grid-template-columns: 40px 1fr;
            }

            .attachments {
                grid-template-columns: 1fr;
            }
        }

        /* Code block styling */
        pre {
            background-color: var(--discord-darkest);
            border-radius: 4px;
            padding: 10px;
            overflow-x: auto;
            margin: 8px 0;
        }

        code {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            color: var(--discord-light);
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--discord-darkest);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--discord-dark);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--discord-accent);
        }

        /* Watermark styling */
        .watermark {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-45deg);
            font-size: 48px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.03);
            white-space: nowrap;
            pointer-events: none;
            user-select: none;
            z-index: 1000;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
        }

        .watermark::before {
            content: "FakePixel Giveaways Carry Support";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(45deg, transparent, rgba(255, 255, 255, 0.05), transparent);
            animation: shimmer 3s infinite;
        }

        @keyframes shimmer {
            0% {
                background-position: -200% 0;
            }
            100% {
                background-position: 200% 0;
            }
        }
        """

    def _get_discord_js(self) -> str:
        """Get enhanced JavaScript for interactive features"""
        return """
        document.addEventListener('DOMContentLoaded', function() {
            // Add hover effects to messages
            const messages = document.querySelectorAll('.message');
            messages.forEach(message => {
                message.addEventListener('mouseenter', function() {
                    this.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                });
                message.addEventListener('mouseleave', function() {
                    this.style.backgroundColor = '';
                });
            });

            // Add click handlers for attachments
            const attachments = document.querySelectorAll('.attachment');
            attachments.forEach(attachment => {
                attachment.addEventListener('click', function() {
                    const url = this.getAttribute('data-url');
                    if (url) {
                        window.open(url, '_blank');
                    }
                });
            });

            // Add copy button for code blocks
            const codeBlocks = document.querySelectorAll('pre code');
            codeBlocks.forEach(block => {
                const button = document.createElement('button');
                button.className = 'copy-button';
                button.textContent = 'Copy';
                button.style.cssText = `
                    position: absolute;
                    top: 5px;
                    right: 5px;
                    padding: 4px 8px;
                    background-color: var(--discord-accent);
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    opacity: 0;
                    transition: opacity 0.2s;
                `;
                
                const pre = block.parentElement;
                pre.style.position = 'relative';
                pre.appendChild(button);

                pre.addEventListener('mouseenter', () => {
                    button.style.opacity = '1';
                });
                pre.addEventListener('mouseleave', () => {
                    button.style.opacity = '0';
                });

                button.addEventListener('click', async () => {
                    try {
                        await navigator.clipboard.writeText(block.textContent);
                        button.textContent = 'Copied!';
                        setTimeout(() => {
                            button.textContent = 'Copy';
                        }, 2000);
                    } catch (err) {
                        console.error('Failed to copy text: ', err);
                    }
                });
            });

            // Add timestamp tooltips
            const timestamps = document.querySelectorAll('.timestamp');
            timestamps.forEach(timestamp => {
                const date = new Date(timestamp.getAttribute('data-timestamp'));
                timestamp.title = date.toLocaleString();
            });

            // Add image preview for attachments
            const images = document.querySelectorAll('.attachment[data-type="image"]');
            images.forEach(image => {
                image.style.cursor = 'pointer';
                image.addEventListener('click', function() {
                    const url = this.getAttribute('data-url');
                    if (url) {
                        const modal = document.createElement('div');
                        modal.style.cssText = `
                            position: fixed;
                            top: 0;
                            left: 0;
                            width: 100%;
                            height: 100%;
                            background-color: rgba(0, 0, 0, 0.8);
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            z-index: 1000;
                        `;
                        
                        const img = document.createElement('img');
                        img.src = url;
                        img.style.cssText = `
                            max-width: 90%;
                            max-height: 90%;
                            object-fit: contain;
                        `;
                        
                        modal.appendChild(img);
                        document.body.appendChild(modal);
                        
                        modal.addEventListener('click', () => {
                            modal.remove();
                        });
                    }
                });
            });

            // Add search functionality
            const searchInput = document.createElement('input');
            searchInput.type = 'text';
            searchInput.placeholder = 'Search messages...';
            searchInput.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 8px 12px;
                background-color: var(--discord-darkest);
                color: var(--discord-light);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                font-size: 14px;
                width: 200px;
                z-index: 100;
            `;
            
            document.body.appendChild(searchInput);

            searchInput.addEventListener('input', function() {
                const searchTerm = this.value.toLowerCase();
                messages.forEach(message => {
                    const content = message.textContent.toLowerCase();
                    message.style.display = content.includes(searchTerm) ? '' : 'none';
                });
            });
        });
        """

    def _generate_feedback_section(self, ticket_data: Dict[str, Any]) -> str:
        """Generate feedback section HTML"""
        feedback = ticket_data.get('feedback', {})
        if not feedback:
            return ''

        rating = feedback.get('rating', 0)
        stars = '⭐' * rating + '☆' * (5 - rating)
        
        return f"""
        <div class="feedback-section">
            <h2 class="feedback-title">Customer Feedback</h2>
            <div class="rating">{stars}</div>
            <div class="feedback-content">
                {feedback.get('comment', 'No comment provided')}
            </div>
        </div>
        """