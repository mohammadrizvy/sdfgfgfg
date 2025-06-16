import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime
from . import storage

logger = logging.getLogger('discord')

class TicketControlsView(discord.ui.View):
    """Main ticket controls with claim and close buttons"""
    def __init__(self, bot, ticket_number: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_number = ticket_number
        self.message = None
        
        # Get initial claim status for persistent view setup
        ticket_data = storage.get_ticket_log(self.ticket_number)
        initial_claimer = ticket_data.get('claimed_by') if ticket_data else "Unclaimed"

        # Add claim/unclaim button
        self.claim_button = discord.ui.Button(
            label="Claim Ticket" if initial_claimer == "Unclaimed" else "Unclaim Ticket",
            style=discord.ButtonStyle.success if initial_claimer == "Unclaimed" else discord.ButtonStyle.danger,
            emoji="🙋" if initial_claimer == "Unclaimed" else "❌",
            custom_id=f"claim_{ticket_number}",
            row=0
        )
        self.claim_button.callback = self.claim_ticket_callback
        self.add_item(self.claim_button)
        
        # Add call for help button
        self.call_help_button = discord.ui.Button(
            label="📞 Call for Help",
            style=discord.ButtonStyle.secondary,
            custom_id=f"call_help_{ticket_number}",
            row=0
        )
        self.call_help_button.callback = self.call_help_callback
        self.add_item(self.call_help_button)
        
        # Add close ticket button
        self.close_button = discord.ui.Button(
            label="Close Ticket",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"close_{ticket_number}",
            row=1
        )
        self.close_button.callback = self.close_ticket_callback
        self.add_item(self.close_button)

    async def claim_ticket_callback(self, interaction: discord.Interaction):
        """Handle claim/unclaim ticket button"""
        try:
            # Get ticket data
            ticket_data = storage.get_ticket_log(self.ticket_number)
            if not ticket_data:
                await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
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
            if not required_role or not any(role.name in [required_role, "Admin", "Staff"] for role in interaction.user.roles):
                await interaction.response.send_message(
                    "❌ Only authorized staff can claim tickets for this category.", 
                    ephemeral=True
                )
                return

            # Get current claim status
            current_claimer = storage.get_ticket_claimed_by(self.ticket_number)
            
            if current_claimer == "Unclaimed":
                # Claim the ticket
                storage.claim_ticket(self.ticket_number, interaction.user.display_name)
                storage.update_ticket_times(self.ticket_number, "claimed", str(interaction.user.id))
                
                # Update button to unclaim
                self.claim_button.label = "Unclaim Ticket"
                self.claim_button.style = discord.ButtonStyle.danger
                self.claim_button.emoji = "❌"
                
                # Update embed
                await self.update_ticket_embed(interaction, claimed_by=interaction.user.display_name)
                
                # Update the view
                await interaction.response.edit_message(view=self)
                
                # Send claim notification
                embed = discord.Embed(
                    title="✅ Ticket Claimed",
                    description=f"Ticket has been claimed by {interaction.user.mention}",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                await interaction.followup.send(embed=embed)
                
                logger.info(f"Ticket {self.ticket_number} claimed by {interaction.user.name}")
                
            elif current_claimer == interaction.user.display_name:
                # Unclaim the ticket
                storage.claim_ticket(self.ticket_number, "Unclaimed")
                
                # Update button to claim
                self.claim_button.label = "Claim Ticket"
                self.claim_button.style = discord.ButtonStyle.success
                self.claim_button.emoji = "🙋"
                
                # Update embed
                await self.update_ticket_embed(interaction, claimed_by="Unclaimed")
                
                # Update the view
                await interaction.response.edit_message(view=self)
                
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
                # Someone else has claimed it
                await interaction.response.send_message(
                    f"❌ This ticket is already claimed by **{current_claimer}**.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in claim_ticket_callback: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while processing the claim.", 
                ephemeral=True
            )

    async def call_help_callback(self, interaction: discord.Interaction):
        """Handle call for help button"""
        try:
            # Get ticket data
            ticket_data = storage.get_ticket_log(self.ticket_number)
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
                pass  # Ignore if we can't send the response

    async def update_ticket_embed(self, interaction: discord.Interaction, claimed_by: str = None):
        """Update the ticket embed with new claim information"""
        try:
            # Get the original embed from the message
            if not self.message:
                return
                
            embed = self.message.embeds[0] if self.message.embeds else None
            if not embed:
                return
            
            # Fetch the latest ticket data from the database
            latest_ticket_data = await storage.get_ticket_log(self.ticket_number)
            if not latest_ticket_data:
                logger.warning(f"Could not fetch latest ticket data for {self.ticket_number} in update_ticket_embed.")
                return

            # Use the claimed_by status from the latest ticket data
            current_claimed_by = latest_ticket_data.get('claimed_by', 'Unclaimed')
            
            # Find and update the ticket information field
            for i, field in enumerate(embed.fields):
                if "Ticket Information" in field.name:
                    # Get the category from the existing field
                    field_lines = field.value.split('\n')
                    category_line = next((line for line in field_lines if "Category:" in line), "**Category:** Unknown")
                    category = category_line.split('**Category:** ')[1] if '**Category:** ' in category_line else "Unknown"
                    
                    # Update the field value with new claim status
                    status_text = f"✅ Claimed by {current_claimed_by}" if current_claimed_by != "Unclaimed" else "🔄 Awaiting Response"
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
            # Store feedback
            logger.info(f"Storing feedback for ticket {self.ticket_number} from user {self.user.name}")
            
            stored = storage.store_feedback(
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
            ticket_data = storage.get_ticket_log(self.ticket_number)
            
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
            # Customize message based on rating
            if self.rating >= 4:
                title = "🌟 Thank You for the Great Feedback!"
                description = "We're thrilled to hear about your positive experience!"
                color = discord.Color.green()
            elif self.rating >= 3:
                title = "💙 Thank You for Your Feedback!"
                description = "We appreciate you taking the time to share your experience."
                color = discord.Color.blue()
            else:
                title = "🔧 Thank You for Helping Us Improve!"
                description = "Your feedback is valuable and will help us provide better service."
                color = discord.Color.orange()

            thank_you_embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.utcnow()
            )
            
            # Add feedback summary
            thank_you_embed.add_field(
                name="📋 Your Feedback Summary",
                value=f"**Rating:** {'⭐' * self.rating} ({self.rating}/5)",
                inline=False
            )
            
            thank_you_embed.add_field(
                name="💭 What You Shared",
                value=f"*\"{self.feedback.value[:100]}{'...' if len(self.feedback.value) > 100 else ''}\"*",
                inline=False
            )
            
            if self.suggestions.value:
                thank_you_embed.add_field(
                    name="💡 Your Suggestions",
                    value=f"*\"{self.suggestions.value[:100]}{'...' if len(self.suggestions.value) > 100 else ''}\"*",
                    inline=False
                )
            
            thank_you_embed.add_field(
                name="🚀 What Happens Next?",
                value=(
                    "• Your feedback has been shared with our team\n"
                    "• We'll use it to improve our support services\n"
                    "• Feel free to create another ticket if you need help!"
                ),
                inline=False
            )
            
            thank_you_embed.set_footer(
                text=f"Ticket #{self.ticket_number} • Your voice matters to us!",
                icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None
            )
            
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
            ticket_data = storage.get_ticket_log(self.ticket_number)
            if not ticket_data:
                await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
                return

            # Defer the response since closing might take some time
            await interaction.response.defer(ephemeral=True)

            try:
                # Update ticket resolution time
                storage.update_ticket_times(self.ticket_number, "resolved", str(interaction.user.id))
                
                # Close the ticket in storage
                storage.close_ticket(self.ticket_number, self.reason.value)
                
                # Send closing message to the channel
                await interaction.channel.send(
                    embed=discord.Embed(
                        title="🔒 Ticket Closing",
                        description=(
                            f"This ticket will be deleted in 10 seconds...\n\n"
                            f"**Close Reason:** {self.reason.value}\n"
                            f"**Closed by:** {interaction.user.mention}"
                        ),
                        color=discord.Color.blue()
                    )
                )
                
                # Send transcript to logs channel if it exists
                transcript_channel = discord.utils.get(interaction.guild.channels, name="ticket-transcripts")
                if transcript_channel:
                    try:
                        # Get all messages from the ticket channel
                        messages = []
                        async for msg in interaction.channel.history(limit=None, oldest_first=True):
                            messages.append(msg)
                        
                        # Create transcript content
                        transcript_content = self.format_transcript(messages, ticket_data, interaction.user)
                        
                        # Save transcript to file
                        import os
                        os.makedirs('transcripts', exist_ok=True)
                        transcript_file = f"transcripts/ticket_{self.ticket_number}.txt"
                        
                        with open(transcript_file, 'w', encoding='utf-8') as f:
                            f.write(transcript_content)
                        
                        # Send transcript to channel
                        with open(transcript_file, 'rb') as f:
                            file = discord.File(f, filename=f"ticket_{self.ticket_number}_transcript.txt")
                            
                            transcript_embed = discord.Embed(
                                title="📋 Ticket Transcript",
                                description=f"Transcript for ticket #{self.ticket_number}",
                                color=discord.Color.blue(),
                                timestamp=datetime.utcnow()
                            )
                            transcript_embed.add_field(
                                name="Ticket Information",
                                value=(
                                    f"**Category:** {ticket_data.get('category', 'Unknown')}\n"
                                    f"**Creator:** <@{ticket_data.get('creator_id', 'Unknown')}>\n"
                                    f"**Claimed By:** {ticket_data.get('claimed_by', 'Unclaimed')}\n"
                                    f"**Closed By:** {interaction.user.mention}\n"
                                    f"**Close Reason:** {self.reason.value}"
                                ),
                                inline=False
                            )
                            
                            await transcript_channel.send(embed=transcript_embed, file=file)
                        
                    except Exception as transcript_error:
                        logger.error(f"Error creating transcript: {transcript_error}")
                
                # Send feedback request to user
                try:
                    creator_id = ticket_data.get('creator_id') or ticket_data.get('user_id')
                    if creator_id:
                        creator = await interaction.guild.fetch_member(int(creator_id))
                        if creator:
                            view = StarRatingView(self.ticket_number, int(creator_id))
                            
                            feedback_embed = discord.Embed(
                                title="⭐ Rate Your Experience",
                                description=(
                                    f"Hi {creator.name}! Your ticket **#{self.ticket_number}** has been closed.\n\n"
                                    f"We'd love to hear about your experience with our support team!"
                                ),
                                color=discord.Color.gold()
                            )
                            
                            try:
                                await creator.send(embed=feedback_embed, view=view)
                            except discord.Forbidden:
                                logger.warning(f"Could not send feedback request to {creator.name} - DMs closed")
                                
                except Exception as feedback_error:
                    logger.error(f"Error sending feedback request: {feedback_error}")
                
                # Wait before deleting the channel
                await asyncio.sleep(10)
                
                # Delete the channel
                await interaction.channel.delete()
                
                logger.info(f"Ticket {self.ticket_number} closed successfully by {interaction.user.name}")
                
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

    def format_transcript(self, messages: list, ticket_data: dict, closed_by: discord.Member) -> str:
        """Format ticket messages into a readable transcript"""
        lines = []
        lines.append("=" * 70)
        lines.append("FAKEPIXEL GIVEAWAYS - TICKET TRANSCRIPT")
        lines.append("=" * 70)
        lines.append(f"TICKET NUMBER: #{self.ticket_number}")
        lines.append(f"CATEGORY: {ticket_data.get('category', 'Unknown')}")
        lines.append(f"CREATOR: {ticket_data.get('creator_id', 'Unknown')}")
        lines.append(f"CLAIMED BY: {ticket_data.get('claimed_by', 'Unclaimed')}")
        lines.append(f"CLOSED BY: {closed_by.name}")
        lines.append(f"CLOSE REASON: {self.reason.value}")
        lines.append(f"GENERATED: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("=" * 70)
        lines.append("")
        
        for msg in messages:
            try:
                timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
                author = msg.author.display_name if hasattr(msg.author, 'display_name') else str(msg.author)
                content = msg.content or "*[attachment or embed]*"
                
                # Clean up content for transcript
                content = content.replace('\n', ' ').strip()
                if len(content) > 100:
                    content = content[:97] + "..."
                    
                lines.append(f"[{timestamp}] {author}: {content}")
            except Exception as e:
                logger.error(f"Error formatting message for transcript: {e}")
                continue
        
        lines.append("")
        lines.append("=" * 70)
        lines.append("END OF TRANSCRIPT")
        lines.append("=" * 70)
        
        return "\n".join(lines)
            