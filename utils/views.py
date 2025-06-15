import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime
from . import storage
from .ticket_closing import TicketClosingSystem

logger = logging.getLogger('discord')

class TicketControlsView(discord.ui.View):
    """Main ticket controls with claim and close buttons"""
    def __init__(self, bot, ticket_number: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_number = ticket_number
        self.message = None
        
        # Add claim/unclaim button
        self.claim_button = discord.ui.Button(
            label="Claim Ticket",
            style=discord.ButtonStyle.success,
            emoji="🙋",
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
                "Master Dungeon Carry": "Master Dungeon Carrier"
            }
            
            required_role = carrier_roles.get(category)
            if not required_role or not any(role.name == required_role for role in interaction.user.roles):
                await interaction.response.send_message(
                    "❌ Only carrier staff can claim tickets for this category.", 
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

            # Get the category from the embed
            embed = interaction.message.embeds[0]
            category = None
            for field in embed.fields:
                if "Ticket Information" in field.name:
                    category = field.value.split('**Category:** ')[1].split('\n')[0]
                    break

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
            
            # Update the ticket embed to remove the status
            if self.message and self.message.embeds:
                embed = self.message.embeds[0]
                for i, field in enumerate(embed.fields):
                    if "Ticket Information" in field.name:
                        # Remove the status line from the field value
                        field_value = field.value.split('\n')
                        field_value = [line for line in field_value if "Status:" not in line]
                        field_value = '\n'.join(field_value)
                        embed.set_field_at(i, name=field.name, value=field_value, inline=field.inline)
                        break
                await self.message.edit(embed=embed)
            
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

            # Get ticket data
            ticket_data = storage.get_ticket_log(self.ticket_number)
            if not ticket_data:
                await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
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
                
            # Find and update the ticket information field
            for i, field in enumerate(embed.fields):
                if "Ticket Information" in field.name:
                    # Update the field value with new claim status
                    field_value = (
                        f"**Ticket #:** {self.ticket_number}\n"
                        f"**Category:** {field.value.split('**Category:** ')[1].split('\n')[0]}\n"
                        f"**Status:** {claimed_by if claimed_by != 'Unclaimed' else '🔄 Awaiting Response'}"
                    )
                    embed.set_field_at(i, name=field.name, value=field_value, inline=field.inline)
                    break
            
            # Update the message with new embed
            await self.message.edit(embed=embed)
            
            # Ensure footer icon is not set during updates
            embed.set_footer(icon_url=None)
            
        except Exception as e:
            logger.error(f"Error updating ticket embed: {e}")

    async def send_feedback_request(self, user: discord.Member, ticket_number: str):
        """Send feedback request to user via DM"""
        try:
            # Check if feedback already exists
            existing_feedback = storage.get_feedback(ticket_number)
            if existing_feedback:
                logger.info(f"Feedback already exists for ticket {ticket_number}")
                return

            # Get ticket data
            ticket_data = storage.get_ticket_log(ticket_number)
            if not ticket_data:
                logger.error(f"Could not find ticket data for {ticket_number}")
                return

            # Create feedback embed
            embed = discord.Embed(
                title="⭐ Rate Your Support Experience",
                description=(
                    f"Hi {user.name}! Your ticket **#{ticket_number}** has been closed.\n\n"
                    f"We'd love to hear about your experience with our support team. "
                    f"Your feedback helps us improve our services!\n\n"
                    f"**Ticket Details:**\n"
                    f"• **Ticket Number:** #{ticket_number}\n"
                    f"• **Category:** {ticket_data.get('category', 'Unknown')}\n\n"
                    f"🌟 **How to Rate**\n"
                    f"Click the star buttons below to rate your experience:\n"
                    f"⭐ = Poor | ⭐⭐⭐⭐⭐ = Excellent"
                ),
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )

            # Add footer
            embed.set_footer(
                text=f"FakePixel Giveaways • Ticket #{ticket_number} • This feedback form expires in 24 hours",
                icon_url=user.guild.icon.url if user.guild.icon else None
            )

            # Create view with star rating buttons
            view = StarRatingView(ticket_number, user.id, timeout=86400)  # 24 hours
            
            # Send DM with feedback request
            try:
                await user.send(embed=embed, view=view)
                logger.info(f"Feedback request sent to user {user.name} for ticket {ticket_number}")
            except discord.Forbidden:
                logger.warning(f"Could not send feedback request to user {user.name} - DMs are closed")

        except Exception as e:
            logger.error(f"Error in send_feedback_request: {e}")

    async def close_ticket(self, channel: discord.TextChannel, ticket_number: str, closer: discord.Member) -> bool:
        """Close a ticket and handle all related tasks"""
        try:
            # Initialize closing system
            closing_system = TicketClosingSystem(self.bot)
            
            # Create a mock interaction for the closing workflow
            class MockInteraction:
                def __init__(self, channel, user, guild):
                    self.channel = channel
                    self.user = user
                    self.guild = guild
                    self.response = MockResponse()
                    self.followup = MockResponse()

            class MockResponse:
                async def send_message(self, *args, **kwargs):
                    pass
                async def defer(self, *args, **kwargs):
                    pass

            mock_interaction = MockInteraction(channel, closer, channel.guild)
            
            # Run closing workflow
            success = await closing_system.close_ticket_workflow(
                interaction=mock_interaction,
                ticket_number=ticket_number
            )

            if success:
                # Delay before deleting the channel
                await asyncio.sleep(10)
                try:
                    await channel.delete()
                except discord.NotFound:
                    pass  # Channel already deleted
                return True
            return False

        except Exception as e:
            logger.error(f"Error in close_ticket: {e}")
            return False

class StarRatingView(discord.ui.View):
    """Star rating system for ticket feedback"""
    def __init__(self, ticket_number: str, user_id: int, timeout: int = 86400):
        super().__init__(timeout=timeout)
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.add_star_buttons()
    
    def add_star_buttons(self):
        """Add star rating buttons"""
        for rating in range(1, 6):
            button = discord.ui.Button(
                label=f"{rating} Star{'s' if rating > 1 else ''}",
                custom_id=f"star_{rating}",
                emoji="⭐",
                style=discord.ButtonStyle.primary if rating >= 4 else discord.ButtonStyle.secondary,
                row=0 if rating <= 3 else 1
            )
            button.callback = self.create_star_callback(rating)
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
        
        # Customize title based on rating
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
        
        # Add response time rating
        self.response_time = discord.ui.TextInput(
            label="Response Time Rating (1-5)",
            placeholder="How quickly did we respond to your ticket?",
            required=True,
            max_length=1,
            min_length=1
        )
        self.add_item(self.response_time)
        
        # Add staff helpfulness rating
        self.staff_helpfulness = discord.ui.TextInput(
            label="Staff Helpfulness Rating (1-5)",
            placeholder="How helpful was our support staff?",
            required=True,
            max_length=1,
            min_length=1
        )
        self.add_item(self.staff_helpfulness)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate ratings
            try:
                response_rating = int(self.response_time.value)
                helpfulness_rating = int(self.staff_helpfulness.value)
                if not (1 <= response_rating <= 5 and 1 <= helpfulness_rating <= 5):
                    raise ValueError("Ratings must be between 1 and 5")
            except ValueError:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Invalid Rating",
                        description="Please provide valid ratings (1-5) for response time and staff helpfulness.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            # Store feedback
            logger.info(f"Storing feedback for ticket {self.ticket_number} from user {self.user.name}")
            
            stored = storage.store_feedback(
                ticket_name=self.ticket_number,
                user_id=str(self.user.id),
                rating=self.rating,
                feedback=self.feedback.value,
                suggestions=self.suggestions.value,
                carrier_ratings={
                    'response_time': response_rating,
                    'staff_helpfulness': helpfulness_rating
                }
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
            if not ticket_data:
                logger.error(f"Could not find ticket data for {self.ticket_number}")
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="⚠️ Warning",
                        description="Your feedback was saved, but we couldn't find the ticket details.",
                        color=discord.Color.orange()
                    ),
                    ephemeral=True
                )
                return

            # Get the guild and feedback channel
            guild = interaction.guild
            if not guild:
                guild_id = ticket_data.get('guild_id')
                if guild_id:
                    guild = interaction.client.get_guild(int(guild_id))
                
            if not guild:
                logger.error(f"Could not determine guild for ticket {self.ticket_number}")
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="✅ Feedback Saved",
                        description="Thank you for your feedback! It has been saved successfully.",
                        color=discord.Color.green()
                    ),
                    ephemeral=True
                )
                return

            # Find feedback channel
            feedback_channel = discord.utils.get(guild.text_channels, name='feedback-logs')
            
            if feedback_channel:
                # Create enhanced feedback embed for staff
                await self.send_feedback_to_channel(feedback_channel, ticket_data)
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
                    f"**Claimed By:** {ticket_data.get('claimed_by', 'Unclaimed')}\n"
                    f"**Created:** <t:{int(datetime.fromisoformat(ticket_data.get('created_at', datetime.now().isoformat())).timestamp())}:R>"
                ),
                inline=True
            )
            
            # Add ratings breakdown
            response_rating = int(self.response_time.value)
            helpfulness_rating = int(self.staff_helpfulness.value)
            
            feedback_embed.add_field(
                name="📊 Detailed Ratings",
                value=(
                    f"**Overall:** {'⭐' * self.rating} ({self.rating}/5)\n"
                    f"**Response Time:** {'⭐' * response_rating} ({response_rating}/5)\n"
                    f"**Staff Helpfulness:** {'⭐' * helpfulness_rating} ({helpfulness_rating}/5)"
                ),
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
                value=(
                    f"**Overall Rating:** {'⭐' * self.rating} ({self.rating}/5)\n"
                    f"**Response Time:** {'⭐' * int(self.response_time.value)} ({self.response_time.value}/5)\n"
                    f"**Staff Helpfulness:** {'⭐' * int(self.staff_helpfulness.value)} ({self.staff_helpfulness.value}/5)"
                ),
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

class FeedbackDisplayView(discord.ui.View):
    """View to display submitted feedback with management options"""
    
    def __init__(self, ticket_number: str, rating: int):
        super().__init__(timeout=None)
        self.ticket_number = ticket_number
        self.rating = rating
        
        # Add disabled star buttons to show rating
        for i in range(1, 6):
            button = discord.ui.Button(
                style=discord.ButtonStyle.success if i <= rating else discord.ButtonStyle.secondary,
                emoji="⭐",
                label=str(i),
                disabled=True,
                custom_id=f"star_display_{i}",
                row=0
            )
            self.add_item(button)
        
        # Add management buttons for staff
        self.add_item(self.create_respond_button())
        self.add_item(self.create_archive_button())
    
    def create_respond_button(self):
        """Create button for staff to respond to feedback"""
        button = discord.ui.Button(
            label="Respond to Customer",
            style=discord.ButtonStyle.primary,
            emoji="💬",
            custom_id=f"respond_{self.ticket_number}",
            row=1
        )
        
        async def respond_callback(interaction: discord.Interaction):
            # Check if user has staff permissions
            if not any(role.name in ["Staff", "Admin", "Moderator", "Support"] for role in interaction.user.roles):
                await interaction.response.send_message(
                    "❌ You don't have permission to respond to feedback.",
                    ephemeral=True
                )
                return
            
            modal = FeedbackResponseModal(self.ticket_number)
            await interaction.response.send_modal(modal)
        
        button.callback = respond_callback
        return button
    
    def create_archive_button(self):
        """Create button to archive feedback"""
        button = discord.ui.Button(
            label="Archive Feedback",
            style=discord.ButtonStyle.secondary,
            emoji="📁",
            custom_id=f"archive_{self.ticket_number}",
            row=1
        )
        
        async def archive_callback(interaction: discord.Interaction):
            # Check if user has admin permissions
            if not any(role.name in ["Admin", "Moderator"] for role in interaction.user.roles):
                await interaction.response.send_message(
                    "❌ You don't have permission to archive feedback.",
                    ephemeral=True
                )
                return
            
            # Disable all buttons
            for item in self.children:
                if not item.label or "star" not in item.custom_id:
                    item.disabled = True
            
            embed = discord.Embed(
                title="📁 Feedback Archived",
                description=f"Feedback for ticket #{self.ticket_number} has been archived by {interaction.user.mention}",
                color=discord.Color.greyple(),
                timestamp=datetime.utcnow()
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
        
        button.callback = archive_callback
        return button

class FeedbackResponseModal(discord.ui.Modal, title="💬 Respond to Customer Feedback"):
    def __init__(self, ticket_number: str):
        super().__init__()
        self.ticket_number = ticket_number
        
        self.response = discord.ui.TextInput(
            label="Your Response to the Customer",
            placeholder="Thank the customer and address their feedback...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000,
            min_length=10
        )
        self.add_item(self.response)
        
        self.action_taken = discord.ui.TextInput(
            label="Actions Taken (Optional)",
            placeholder="What specific actions have been taken based on this feedback?",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.action_taken)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get the original feedback
            feedback_data = storage.get_feedback(self.ticket_number)
            if not feedback_data:
                await interaction.response.send_message(
                    "❌ Could not find the original feedback.",
                    ephemeral=True
                )
                return
            
            # Get the customer
            customer_id = feedback_data.get('user_id')
            if customer_id:
                try:
                    customer = interaction.guild.get_member(int(customer_id))
                    if customer:
                        # Send response to customer
                        customer_embed = discord.Embed(
                            title="💬 Response to Your Feedback",
                            description=f"Thank you for your feedback on ticket #{self.ticket_number}!",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        
                        customer_embed.add_field(
                            name="📝 Staff Response",
                            value=self.response.value,
                            inline=False
                        )
                        
                        if self.action_taken.value:
                            customer_embed.add_field(
                                name="🔧 Actions Taken",
                                value=self.action_taken.value,
                                inline=False
                            )
                        
                        customer_embed.set_footer(
                            text=f"Response from {interaction.user.display_name}",
                            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
                        )
                        
                        try:
                            await customer.send(embed=customer_embed)
                            status_msg = "✅ Response sent to customer successfully!"
                        except discord.Forbidden:
                            status_msg = "⚠️ Response saved, but couldn't send DM to customer (DMs disabled)."
                        
                    else:
                        status_msg = "⚠️ Customer not found in server."
                        
                except ValueError:
                    status_msg = "⚠️ Invalid customer ID."
            else:
                status_msg = "⚠️ Customer ID not found in feedback data."
            
            await interaction.response.send_message(status_msg, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error submitting feedback response: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while sending your response.",
                ephemeral=True
            )
            
class CloseReasonModal(discord.ui.Modal, title="Close Ticket"):
    def __init__(self, ticket_number: str):
        super().__init__()
        self.ticket_number = ticket_number
        
        self.reason = discord.ui.TextInput(
            label="Reason for Closing",
            placeholder="Please provide a reason for closing this ticket...",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=10
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
                # Close the ticket with the provided reason
                closing_system = TicketClosingSystem(interaction.client)
                success = await closing_system.close_ticket_workflow(
                    interaction=interaction,
                    ticket_number=self.ticket_number,
                    close_reason=self.reason.value
                )
                
                if success:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="✅ Ticket Closed",
                            description=f"Ticket #{self.ticket_number} has been successfully closed and archived.",
                            color=discord.Color.green()
                        ),
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="❌ Error",
                            description="Failed to close the ticket. Please try again or contact an administrator.",
                            color=discord.Color.red()
                        ),
                        ephemeral=True
                    )
            except Exception as e:
                logger.error(f"Error in close ticket workflow: {e}")
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="An error occurred while trying to close the ticket.",
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

            