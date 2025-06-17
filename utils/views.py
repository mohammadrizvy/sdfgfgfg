import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime
from . import storage
from .transcript_manager import TranscriptManager
import os
from discord import ui
from typing import Optional, List, Dict, Any
from utils.responses import create_embed

logger = logging.getLogger('discord')

class TicketControlsView(discord.ui.View):
    """Main ticket controls with claim and close buttons"""
    def __init__(self, bot, ticket_number: Optional[str], initialize_from_db: bool = False):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_number = ticket_number
        self.db = storage.get_db_manager()
        self.transcript_manager = TranscriptManager(bot)
        self.message = None
        self.current_claimer = "Unclaimed"
        self.initialized = False
        
        # Always setup buttons first with default state
        self._setup_buttons()
        
        # Initialize from database if requested
        if initialize_from_db and ticket_number:
            self.load_from_db()

    def load_from_db(self):
        try:
            ticket_info = self.db.get_ticket_info(self.ticket_number)
            if ticket_info:
                self.ticket_number = ticket_info['ticket_number']
        except Exception as e:
            logger.error(f"Error loading ticket info from database: {e}")

    async def _initialize_button_state(self):
        """Initialize button state from database"""
        try:
            ticket_data = await storage.get_ticket_log(self.ticket_number)
            if ticket_data:
                self.current_claimer = ticket_data.get('claimed_by', 'Unclaimed')
            
            # Re-setup buttons with correct state
            self._setup_buttons()
            self.initialized = True
            
            # Update the message if it exists
            if self.message:
                try:
                    await self.message.edit(view=self)
                except Exception as e:
                    logger.error(f"Error updating message after initialization: {e}")
                    
        except Exception as e:
            logger.error(f"Error initializing button state for ticket {self.ticket_number}: {e}")
            self.current_claimer = "Unclaimed"
            self._setup_buttons()
            self.initialized = True

    def _setup_buttons(self):
        """Setup buttons with proper custom IDs for persistence"""
        # Clear existing items
        self.clear_items()
        
        # Determine button state based on current claimer
        if self.current_claimer == "Unclaimed":
            button_label = "Claim Ticket"
            button_style = discord.ButtonStyle.success
            button_emoji = "🙋"
        else:
            button_label = "Unclaim Ticket"
            button_style = discord.ButtonStyle.danger
            button_emoji = "❌"
        
        # Add claim/unclaim button
        self.claim_button = discord.ui.Button(
            label=button_label,
            style=button_style,
            emoji=button_emoji,
            custom_id=f"claim_{self.ticket_number}",
            row=0
        )
        self.claim_button.callback = self.claim_ticket_callback
        self.add_item(self.claim_button)
        
        # Add call for help button
        self.call_help_button = discord.ui.Button(
            label="📞 Call for Help",
            style=discord.ButtonStyle.secondary,
            custom_id=f"call_help_{self.ticket_number}",
            row=0
        )
        self.call_help_button.callback = self.call_help_callback
        self.add_item(self.call_help_button)
        
        # Add close ticket button
        self.close_button = discord.ui.Button(
            label="Close Ticket",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"close_{self.ticket_number}",
            row=1
        )
        self.close_button.callback = self.close_ticket_callback
        self.add_item(self.close_button)

    async def update_claim_button_status(self, claimed_by: str):
        """Update the claim button based on current status"""
        self.current_claimer = claimed_by
        
        # Update button properties
        if claimed_by == "Unclaimed":
            self.claim_button.label = "Claim Ticket"
            self.claim_button.style = discord.ButtonStyle.success
            self.claim_button.emoji = "🙋"
        else:
            self.claim_button.label = "Claimed"
            self.claim_button.style = discord.ButtonStyle.danger
            self.claim_button.emoji = "❌"

    async def claim_ticket_callback(self, interaction: discord.Interaction):
        """Handle claim/unclaim ticket button with proper race condition handling"""
        try:
            # Defer the response to prevent timeout
            await interaction.response.defer()
            
            # Get fresh ticket data from database to prevent race conditions
            ticket_data = await storage.get_ticket_log(self.ticket_number)
            if not ticket_data:
                await interaction.followup.send("❌ Ticket not found.", ephemeral=True)
                return

            # Check if user has carrier role for this category
            category = ticket_data.get('category')
            carrier_roles = {
                "Slayer Carry": "Slayer Carrier",
                "Normal Dungeon Carry": "Normal Dungeon Carrier",
                "Master Dungeon Carry": "Master Dungeon Carrier",
                "Staff Applications": "Admin"
            }
            
            required_role = carrier_roles.get(category)
            if not required_role or not any(role.name in [required_role, "Admin", "Staff", "Moderator"] for role in interaction.user.roles):
                await interaction.followup.send(
                    "❌ Only authorized staff can claim tickets for this category.", 
                    ephemeral=True
                )
                return

            # Get current claim status from database (fresh data)
            current_claimer = ticket_data.get('claimed_by', 'Unclaimed')
            
            if current_claimer == "Unclaimed":
                # Try to claim the ticket
                success = await storage.claim_ticket(self.ticket_number, interaction.user.display_name)
                if success:
                    await storage.update_ticket_times(self.ticket_number, "claimed", str(interaction.user.id))
                    
                    # Update button state
                    await self.update_claim_button_status(interaction.user.display_name)
                    
                    # Update the view on the original message
                    await interaction.edit_original_response(view=self)

                    # Update embed
                    await self.update_ticket_embed(interaction, claimed_by=interaction.user.display_name)
                    
                    # Send claim notification
                    embed = discord.Embed(
                        title="✅ Ticket Claimed",
                        description=f"Ticket has been claimed by {interaction.user.mention}",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    await interaction.followup.send(embed=embed)
                    
                    logger.info(f"Ticket {self.ticket_number} claimed by {interaction.user.name}")
                else:
                    await interaction.followup.send("❌ Failed to claim ticket. It may have been claimed by someone else.", ephemeral=True)
                
            elif current_claimer == interaction.user.display_name:
                # Unclaim the ticket
                success = await storage.claim_ticket(self.ticket_number, "Unclaimed")
                if success:
                    # Update button state
                    await self.update_claim_button_status("Unclaimed")
                    
                    # Update the view on the original message
                    await interaction.edit_original_response(view=self)

                    # Update embed
                    await self.update_ticket_embed(interaction, claimed_by="Unclaimed")
                    
                    # Send unclaim notification
                    embed = discord.Embed(
                        title="🔄 Ticket Unclaimed",
                        description=f"Ticket has been unclaimed by {interaction.user.mention}",
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )
                    await interaction.followup.send(embed=embed)
                    
                    logger.info(f"Ticket {self.ticket_number} unclaimed by {interaction.user.name}")
                else:
                    await interaction.followup.send("❌ Failed to unclaim ticket.", ephemeral=True)
                
            else:
                # Someone else has claimed it
                await interaction.followup.send(
                    f"❌ This ticket is already claimed by **{current_claimer}**.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in claim_ticket_callback: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while processing the claim.", 
                    ephemeral=True
                )
            except:
                pass

    async def call_help_callback(self, interaction: discord.Interaction):
        """Handle call for help button"""
        try:
            # Get ticket data
            ticket_data = await storage.get_ticket_log(self.ticket_number)
            if not ticket_data:
                await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
                return

            # Check if ticket has been open for 2 hours
            creation_time = discord.utils.parse_time(ticket_data.get('created_at'))
            current_time = discord.utils.utcnow()
            time_diff = current_time - creation_time
            
            if time_diff.total_seconds() < 7200:  # 2 hours = 7200 seconds
                hours_left = (7200 - time_diff.total_seconds()) / 3600
                await interaction.response.send_message(
                    f"⏰ The **Call for Help** button can only be used after your ticket has been open for **2 hours** with no carrier response.\n\n"
                    f"**Time remaining:** {hours_left:.1f} hours\n\n"
                    f"*Thank you for your patience! Our carriers will get to you as soon as possible.*",
                    ephemeral=True
                )
                return

            # Get the category from ticket data
            category = ticket_data.get('category')
            if not category:
                await interaction.response.send_message("❌ Could not determine ticket category.", ephemeral=True)
                return

            # Get carrier role name based on category
            carrier_role_name = storage.get_category_role(category)
            if not carrier_role_name:
                await interaction.response.send_message("❌ No carrier role found for this category.", ephemeral=True)
                return

            # Check if a carrier has already responded
            has_carrier_response = False
            async for message in interaction.channel.history(limit=None):
                author = message.author
                if author and any(role.name == carrier_role_name for role in author.roles):
                    has_carrier_response = True
                    break

            if has_carrier_response:
                await interaction.response.send_message(
                    "✅ A carrier has already responded to your ticket! Please check the conversation above.",
                    ephemeral=True
                )
                return

            # Get the carrier role to mention
            carrier_role = discord.utils.get(interaction.guild.roles, name=carrier_role_name)
            if not carrier_role:
                await interaction.response.send_message(f"❌ {carrier_role_name} role not found.", ephemeral=True)
                return

            # Send carrier ping with alert
            ping_embed = discord.Embed(
                title="🚨 Call for Help - Urgent Assistance Needed",
                description=(
                    f"**Ticket:** #{self.ticket_number}\n"
                    f"**Category:** {category}\n"
                    f"**Customer:** {interaction.user.mention}\n"
                    f"**Status:** Open for over 2 hours with no response"
                ),
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            
            ping_embed.add_field(
                name="⚠️ Priority Alert",
                value=(
                    "This ticket requires immediate attention!\n"
                    "Please respond as soon as possible to maintain our service quality."
                ),
                inline=False
            )
            
            await interaction.channel.send(
                content=f"{carrier_role.mention} 🚨",
                embed=ping_embed
            )
            
            await interaction.response.send_message(
                "✅ Help request sent! A carrier will assist you shortly.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in call help callback: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while sending the help request.",
                ephemeral=True
            )

    async def close_ticket_callback(self, interaction: discord.Interaction):
        """Handle ticket closing - staff only"""
        try:
            # Check if user has staff permissions
            if not any(role.name in ["Staff", "Admin", "Moderator", "Carrier"] for role in interaction.user.roles):
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Permission Denied",
                        description="Only staff members can close tickets.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            # Show the close reason modal
            modal = CloseReasonModal(self.ticket_number)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error in close ticket callback: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Error",
                            description="An error occurred while trying to close the ticket.",
                            color=discord.Color.red()
                        ),
                        ephemeral=True
                    )
            except Exception:
                pass

    async def update_ticket_embed(self, interaction: discord.Interaction, claimed_by: str = None):
        """Update the ticket embed with new claim information"""
        try:
            # Get the original embed from the message
            if not self.message:
                return
                
            embed = self.message.embeds[0] if self.message.embeds else None
            if not embed:
                return
            
            # Use the provided claimed_by or fetch from database
            if claimed_by is None:
                latest_ticket_data = await storage.get_ticket_log(self.ticket_number)
                if latest_ticket_data:
                    claimed_by = latest_ticket_data.get('claimed_by', 'Unclaimed')
                else:
                    claimed_by = 'Unclaimed'
            
            # Find and update the ticket information field
            for i, field in enumerate(embed.fields):
                if "Ticket Information" in field.name:
                    # Get the category from the existing field
                    field_lines = field.value.split('\n')
                    category_line = next((line for line in field_lines if "Category:" in line), "**Category:** Unknown")
                    category = category_line.split('**Category:** ')[1] if '**Category:** ' in category_line else "Unknown"
                    
                    # Update the field value with new claim status
                    status_text = f"✅ Claimed by {claimed_by}" if claimed_by != "Unclaimed" else "🔄 Awaiting Response"
                    field_value = (
                        f"**Ticket #:** {self.ticket_number}\n"
                        f"**Category:** {category}\n"
                        f"**Status:** {status_text}"
                    )
                    embed.set_field_at(i, name=field.name, value=field_value, inline=field.inline)
                    break
            
            # Update the message with new embed
            await self.message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error updating ticket embed: {e}")

class StarRatingView(discord.ui.View):
    """Star rating system for ticket feedback"""
    def __init__(self, ticket_number: str, user_id: int, timeout: int = 86400):
        super().__init__(timeout=timeout)
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.add_star_buttons()
    
    def add_star_buttons(self):
        """Add star rating buttons"""
        for i in range(1, 6):
            button = discord.ui.Button(
                label=f"{'⭐' * i} {i} Star{'s' if i > 1 else ''}",
                style=discord.ButtonStyle.primary,
                custom_id=f"star_rating_{self.ticket_number}_{i}"
            )
            button.callback = self.create_star_callback(i)
            self.add_item(button)
    
    def create_star_callback(self, rating: int):
        """Create callback for specific rating"""
        async def star_callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "This feedback form is not for you.", 
                    ephemeral=True
                )
                return
            
            # Create feedback modal
            modal = FeedbackModal(self.ticket_number, rating, interaction.user)
            await interaction.response.send_modal(modal)
        
        return star_callback
    
    async def on_timeout(self):
        """Handle view timeout"""
        try:
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            logger.info(f"Feedback view timed out for ticket {self.ticket_number}")
        except Exception as e:
            logger.error(f"Error handling view timeout: {e}")

class FeedbackModal(discord.ui.Modal, title="✨ Share Your Experience"):
    def __init__(self, ticket_number: str, rating: int, user: discord.Member):
        super().__init__()
        self.ticket_number = ticket_number
        self.rating = rating
        self.user = user
        
        if rating >= 4:
            self.title = "✨ Tell us what went well!"
        elif rating >= 3:
            self.title = "💭 Help us understand your experience"
        else:
            self.title = "🔧 Help us improve our service"
        
        # Add feedback field
        self.feedback = discord.ui.TextInput(
            label="Your Experience",
            placeholder="Please share details about your support experience...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000,
            min_length=10
        )
        self.add_item(self.feedback)
        
        # Add suggestions field
        self.suggestions = discord.ui.TextInput(
            label="Suggestions for Improvement",
            placeholder="How can we make our service even better? (Optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.add_item(self.suggestions)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Store feedback using async function
            logger.info(f"Storing feedback for ticket {self.ticket_number} from user {self.user.name}")
            
            stored = await storage.store_feedback_async(
                ticket_name=self.ticket_number,
                user_id=str(self.user.id),
                rating=self.rating,
                feedback=self.feedback.value,
                suggestions=self.suggestions.value or ""
            )
            
            if not stored:
                logger.error(f"Failed to store feedback for ticket {self.ticket_number}")
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Storage Error",
                        description="Failed to save your feedback. Please try again or contact an administrator.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            # Get ticket data for guild information
            ticket_data = await storage.get_ticket_log(self.ticket_number)
            
            # Get the guild and feedback channel
            guild = interaction.guild
            if not guild and ticket_data:
                guild_id = ticket_data.get('guild_id')
                if guild_id:
                    guild = interaction.client.get_guild(int(guild_id))

            # Find feedback channel and send feedback
            if guild:
                feedback_channel = discord.utils.get(guild.text_channels, name='feedback-logs')
                
                if feedback_channel:
                    # Create enhanced feedback embed for staff
                    await self.send_feedback_to_channel(feedback_channel, ticket_data or {})
                    logger.info(f"Feedback sent to channel {feedback_channel.name} for ticket {self.ticket_number}")
                else:
                    logger.warning(f"Feedback channel not found in guild {guild.name}")

            # Send thank you message to user
            await self.send_thank_you_message(interaction)

        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="An error occurred while submitting your feedback. Please try again later.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

    async def send_feedback_to_channel(self, feedback_channel: discord.TextChannel, ticket_data: dict):
        """Send feedback to the feedback logs channel with enhanced formatting"""
        try:
            # Determine embed color based on rating
            if self.rating >= 4:
                color = discord.Color.green()
                emoji = "🌟"
            elif self.rating >= 3:
                color = discord.Color.gold()
                emoji = "⭐"
            else:
                color = discord.Color.red()
                emoji = "⚠️"

            feedback_embed = discord.Embed(
                title=f"{emoji} Ticket Feedback Received",
                description=f"**Ticket #{self.ticket_number}** • **Overall Rating:** {'⭐' * self.rating}",
                color=color,
                timestamp=datetime.utcnow()
            )
            
            # Add ticket information
            feedback_embed.add_field(
                name="🎫 Ticket Details",
                value=(
                    f"**Category:** {ticket_data.get('category', 'Unknown')}\n"
                    f"**Customer:** {self.user.mention}\n"
                    f"**Claimed By:** {ticket_data.get('claimed_by', 'Unclaimed')}"
                ),
                inline=True
            )
            
            # Add rating info
            feedback_embed.add_field(
                name="📊 Rating",
                value=f"{'⭐' * self.rating} ({self.rating}/5)",
                inline=True
            )
            
            # Add feedback content
            feedback_embed.add_field(
                name="💭 Customer Feedback",
                value=f"```{self.feedback.value}```",
                inline=False
            )
            
            # Add suggestions if provided
            if self.suggestions.value:
                feedback_embed.add_field(
                    name="💡 Suggestions for Improvement",
                    value=f"```{self.suggestions.value}```",
                    inline=False
                )
            
            # Add user avatar as thumbnail
            if self.user.avatar:
                feedback_embed.set_thumbnail(url=self.user.avatar.url)
            
            feedback_embed.set_footer(
                text=f"Feedback ID: {self.ticket_number} • Submitted by {self.user.display_name}",
                icon_url=self.user.avatar.url if self.user.avatar else None
            )
            
            await feedback_channel.send(embed=feedback_embed)
            
        except Exception as e:
            logger.error(f"Error sending feedback to channel: {e}")

    async def send_thank_you_message(self, interaction: discord.Interaction):
        """Send a personalized thank you message to the user"""
        try:
            # Determine the star representation
            stars_display = '⭐' * self.rating + '☆' * (5 - self.rating)

            thank_you_embed = discord.Embed(
                title="Thank you for your rating!",
                description=(
                    f"{interaction.user.mention}, you have successfully rated our Staff's\n" 
                    f"dialog for {stars_display} in Ticket **{self.ticket_number}**. We will for sure improve thanks to\n" 
                    "your reviews!"
                ),
                color=discord.Color.from_rgb(47, 49, 54) # Dark Discord-like color
            )

            # Add feedback comment
            comment_text = self.feedback.value if self.feedback.value else "No comment provided."
            thank_you_embed.add_field(
                name="Here's what you wrote in review:",
                value=f"""```\n{comment_text}\n```""",
                inline=False
            )

            # Set thumbnail from provided image
            thank_you_embed.set_thumbnail(url="https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo")

            # No footer needed as per the image

            await interaction.response.send_message(embed=thank_you_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error sending thank you message: {e}")
            # Fallback simple message
            try:
                await interaction.response.send_message(
                    "✅ Thank you for your feedback! It has been submitted successfully.",
                    ephemeral=True
                )
            except:
                pass

class CloseReasonModal(discord.ui.Modal, title="Close Ticket"):
    def __init__(self, ticket_number: str):
        super().__init__()
        self.ticket_number = ticket_number
        
        self.reason = discord.ui.TextInput(
            label="Reason for Closing",
            placeholder="Please provide a reason for closing this ticket...",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=5,
            max_length=500
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get ticket data
            ticket_data = await storage.get_ticket_log(self.ticket_number)
            if not ticket_data:
                await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
                return

            # Defer the response since closing might take some time
            await interaction.response.defer(ephemeral=True)

            try:
                # Update ticket resolution time
                await storage.update_ticket_times(self.ticket_number, "resolved", str(interaction.user.id))
                
                # Close the ticket in storage
                await storage.close_ticket(self.ticket_number, self.reason.value)
                
                # Send closing message to the channel
                await interaction.channel.send(
                    embed=discord.Embed(
                        title="🔒 Ticket Closing",
                        description=(
                            f"This ticket will be deleted in 10 seconds...\n\n"
                            f"**Close Reason:** {self.reason.value}\n"
                            f"**Closed by:** {interaction.user.mention}\n\n"
                            f"📋 **Generating transcript...** Please wait..."
                        ),
                        color=discord.Color.blue()
                    )
                )
                
                # Get all messages from the ticket channel
                messages = []
                async for msg in interaction.channel.history(limit=None, oldest_first=True):
                    messages.append(msg)
                
                # Initialize transcript manager
                transcript_manager = TranscriptManager(interaction.client)
                
                # Generate comprehensive transcript (both HTML and text)
                transcript_results = await transcript_manager.generate_comprehensive_transcript(
                    self.ticket_number, messages, ticket_data
                )
                
                # Send transcript to logs channel if it exists
                transcript_channel = discord.utils.get(interaction.guild.channels, name="ticket-transcripts")
                if transcript_channel:
                    try:
                        # Create enhanced transcript embed
                        transcript_embed = discord.Embed(
                            title=f"📋 Ticket #{self.ticket_number} Transcript",
                            description="A detailed record of the ticket conversation has been generated.",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )

                        # Add ticket information
                        transcript_embed.add_field(
                            name="🎫 Ticket Details",
                            value=(
                                f"**Category:** {ticket_data.get('category', 'Unknown')}\n"
                                f"**Created by:** <@{ticket_data.get('creator_id', 'Unknown')}>\n"
                                f"**Claimed by:** {f'<@{ticket_data.get('claimed_by')}>' if ticket_data.get('claimed_by') else 'Unclaimed'}\n"
                                f"**Created:** <t:{int(datetime.fromisoformat(ticket_data.get('created_at', datetime.utcnow().isoformat()).replace('Z', '+00:00')).timestamp())}:R>"
                            ),
                            inline=True
                        )

                        # Add conversation stats
                        staff_messages = sum(1 for msg in messages if any(role.name in ["Staff", "Admin", "Moderator", "Carrier"] for role in msg.author.roles))
                        user_messages = len(messages) - staff_messages
                        
                        transcript_embed.add_field(
                            name="📊 Conversation Stats",
                            value=(
                                f"**Total Messages:** {len(messages)}\n"
                                f"**Staff Messages:** {staff_messages}\n"
                                f"**User Messages:** {user_messages}\n"
                                f"**Participants:** {len(set(msg.author.id for msg in messages))}"
                            ),
                            inline=True
                        )

                        # Add timing information
                        created_time = ticket_data.get('created_at', 'Unknown')
                        if created_time != 'Unknown':
                            try:
                                created_dt = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                                duration = datetime.utcnow() - created_dt.replace(tzinfo=None)
                                duration_str = f"{duration.days}d {duration.seconds//3600}h {(duration.seconds//60)%60}m"
                            except:
                                duration_str = "Unknown"
                        else:
                            duration_str = "Unknown"

                        transcript_embed.add_field(
                            name="⏰ Timing Info",
                            value=(
                                f"**Created:** <t:{int(created_dt.timestamp())}:R>\n"
                                f"**Duration:** {duration_str}\n"
                                f"**Closed:** <t:{int(datetime.utcnow().timestamp())}:f>"
                            ),
                            inline=False
                        )

                        # Add transcript information
                        transcript_embed.add_field(
                            name="📄 Transcript",
                            value="A detailed text transcript has been attached to this message.",
                            inline=False
                        )

                        # Add footer with branding
                        transcript_embed.set_footer(
                            text="FakePixel Giveaways • Enhanced Transcript System",
                            icon_url="https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo"
                        )

                        # Send transcript embed with file
                        files = []
                        if transcript_results.get('text_file'):
                            # Create Discord file object from the filepath
                            filepath = transcript_results['text_file']
                            filename = os.path.basename(filepath)
                            files.append(discord.File(filepath, filename=filename))
                        
                        await transcript_channel.send(embed=transcript_embed, files=files)
                        
                        # Store transcript metadata
                        await transcript_manager.store_transcript_metadata(self.ticket_number, {
                            'ticket_number': self.ticket_number,
                            'text_file': transcript_results['text_file'] if transcript_results.get('text_file') else None, # Store the filepath
                            'message_count': len(messages),
                            'participants': list(set(str(msg.author.id) for msg in messages))
                        })
                        
                    except Exception as transcript_error:
                        logger.error(f"Error sending transcript: {transcript_error}")
                        # Send fallback message
                        await transcript_channel.send(
                            embed=discord.Embed(
                                title="⚠️ Transcript Generation Error",
                                description=f"Failed to generate transcript for ticket #{self.ticket_number}",
                                color=discord.Color.orange()
                            )
                        )
                
                # Send feedback request to user
                try:
                    creator_id = ticket_data.get('creator_id') or ticket_data.get('user_id')
                    if creator_id:
                        creator = await interaction.guild.fetch_member(int(creator_id))
                        if creator:
                            view = StarRatingView(self.ticket_number, int(creator_id))
                            
                            feedback_embed = discord.Embed(
                                title="🌟 Your Feedback Matters! Rate Your Service 🌟",
                                description=(
                                    f"Hello {creator.name}! Your ticket **#{self.ticket_number}** has been successfully closed.\n\n"
                                    "We hope you had a great experience with our support team. Your feedback helps us improve and provide even better service!\n\n"
                                    "Please take a moment to rate your overall experience below. It's quick, easy, and incredibly valuable to us!"
                                ),
                                color=discord.Color.from_rgb(255, 215, 0)
                            )
                            
                            # Add transcript link to feedback if available
                            # Removed as per user request to attach file directly
                            # if transcript_results.get('text_file'):
                            #     feedback_embed.add_field(
                            #         name="📄 Your Transcript",
                            #         value="📄 **Text Transcript** (attached)",
                            #         inline=False
                            #     )
                            
                            feedback_embed.add_field(
                                name="💡 Why Your Feedback is Important",
                                value="Your ratings and comments help us identify areas of improvement, recognize outstanding staff, and enhance our services for everyone.",
                                inline=False
                            )
                            
                            feedback_embed.add_field(
                                name="✅ What Happens Next?",
                                value=(
                                    "Once you submit your rating, your feedback will be reviewed by our team. "
                                    "Thank you for helping us grow!"
                                ),
                                inline=False
                            )

                            feedback_embed.set_footer(
                                text="FakePixel Giveaways • Customer Satisfaction Survey",
                                icon_url="https://i.imgur.com/your-logo.png" # Replace with your logo URL
                            )

                            # Send feedback embed with rating view and transcript file
                            # Ensure the file is a discord.File object
                            transcript_file_to_send = None
                            transcript_filepath = transcript_results.get('text_file')
                            if transcript_filepath and os.path.exists(transcript_filepath):
                                transcript_file_to_send = discord.File(transcript_filepath, filename=os.path.basename(transcript_filepath))

                            await creator.send(
                                embed=feedback_embed,
                                view=view,
                                file=transcript_file_to_send
                            )
                            logger.info(f"Sent feedback request to creator {creator.name} for ticket {self.ticket_number}")
                            
                except Exception as feedback_error:
                    logger.error(f"Error sending feedback request: {feedback_error}")
                
                # Store the ticket log with all messages
                await storage.store_ticket_log(
                    ticket_number=self.ticket_number,
                    messages=messages,
                    creator_id=ticket_data.get('creator_id'),
                    category=ticket_data.get('category'),
                    claimed_by=ticket_data.get('claimed_by'),
                    closed_by=str(interaction.user.id),
                    details=ticket_data.get('details'),
                    guild_id=interaction.guild.id,
                    close_reason=self.reason.value
                )
                
                # Update the closing message with transcript status
                await interaction.channel.send(
                    embed=discord.Embed(
                        title="✅ Transcript Generated Successfully",
                        description=(
                            f"📋 Transcript has been generated and saved!\n"
                            f"🔗 Check {transcript_channel.mention if transcript_channel else '#ticket-transcripts'} for the full transcript\n\n"
                            f"⏰ Channel will be deleted in 5 seconds..."
                        ),
                        color=discord.Color.green()
                    )
                )
                
                # Wait before deleting the channel
                await asyncio.sleep(10)
                
                # Delete the channel
                await interaction.channel.delete()
                
                logger.info(f"Ticket {self.ticket_number} closed successfully by {interaction.user.name} with enhanced transcript")
                
            except Exception as close_error:
                logger.error(f"Error in close ticket workflow: {close_error}")
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="An error occurred while closing the ticket.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in close reason modal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="An error occurred while trying to close the ticket.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This button can only be used in ticket channels.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            ticket_number = channel_name.split("-")[1]
            
            await self.transcript_manager.create_transcript(interaction.channel, ticket_number)
            await interaction.channel.delete()
            
            await self.db.close_ticket(ticket_number)
            
            logger.info(f"Ticket {ticket_number} closed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in close_ticket button: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while closing the ticket.",
                    "error"
                ),
                ephemeral=True
            )

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.primary, custom_id="add_user")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This button can only be used in ticket channels.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            modal = AddUserModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in add_user button: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while processing your request.",
                    "error"
                ),
                ephemeral=True
            )

    @discord.ui.button(label="Remove User", style=discord.ButtonStyle.secondary, custom_id="remove_user")
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This button can only be used in ticket channels.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            modal = RemoveUserModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in remove_user button: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while processing your request.",
                    "error"
                ),
                ephemeral=True
            )

    @discord.ui.button(label="Rename Ticket", style=discord.ButtonStyle.success, custom_id="rename_ticket")
    async def rename_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This button can only be used in ticket channels.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            modal = RenameTicketModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in rename_ticket button: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while processing your request.",
                    "error"
                ),
                ephemeral=True
            )

class AddUserModal(ui.Modal, title="Add User to Ticket"):
    def __init__(self):
        super().__init__()
        self.user_id = ui.TextInput(
            label="User ID",
            placeholder="Enter the user's ID",
            required=True
        )
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id.value)
            user = interaction.guild.get_member(user_id)
            
            if not user:
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "User not found in the server.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
            
            await interaction.response.send_message(
                embed=create_embed(
                    "Success",
                    f"Added {user.mention} to the ticket.",
                    "success"
                )
            )
            
            logger.info(f"User {user.name} added to ticket {interaction.channel.name} by {interaction.user.name}")
            
        except ValueError:
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "Invalid user ID format.",
                    "error"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in AddUserModal: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while adding the user.",
                    "error"
                ),
                ephemeral=True
            )

class RemoveUserModal(ui.Modal, title="Remove User from Ticket"):
    def __init__(self):
        super().__init__()
        self.user_id = ui.TextInput(
            label="User ID",
            placeholder="Enter the user's ID",
            required=True
        )
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id.value)
            user = interaction.guild.get_member(user_id)
            
            if not user:
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "User not found in the server.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            await interaction.channel.set_permissions(user, overwrite=None)
            
            await interaction.response.send_message(
                embed=create_embed(
                    "Success",
                    f"Removed {user.mention} from the ticket.",
                    "success"
                )
            )
            
            logger.info(f"User {user.name} removed from ticket {interaction.channel.name} by {interaction.user.name}")
            
        except ValueError:
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "Invalid user ID format.",
                    "error"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in RemoveUserModal: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while removing the user.",
                    "error"
                ),
                ephemeral=True
            )

class RenameTicketModal(ui.Modal, title="Rename Ticket"):
    def __init__(self):
        super().__init__()
        self.new_name = ui.TextInput(
            label="New Name",
            placeholder="Enter the new ticket name",
            required=True
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This modal can only be used in ticket channels.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            ticket_number = channel_name.split("-")[1]
            new_channel_name = f"ticket-{ticket_number}-{self.new_name.value}"
            
            await interaction.channel.edit(name=new_channel_name)
            
            await interaction.response.send_message(
                embed=create_embed(
                    "Success",
                    f"Ticket renamed to: {new_channel_name}",
                    "success"
                )
            )
            
            logger.info(f"Ticket {ticket_number} renamed to {new_channel_name} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in RenameTicketModal: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while renaming the ticket.",
                    "error"
                ),
                ephemeral=True
            )