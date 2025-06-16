import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone

# Import utils
from utils import storage
from utils.views import TicketControlsView

logger = logging.getLogger('discord')

class TicketCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_categories = ['Slayer Carry', 'Normal Dungeon Carry', 'Master Dungeon Carry', 'Staff Applications']
        logger.info("TicketCommands cog initialized")
        
        # Add message event listener
        self.bot.add_listener(self.on_message, 'on_message')

    async def create_ticket_channel(self, interaction: discord.Interaction, category: str, details: Optional[str] = None):
        """Create a ticket channel for the user"""
        try:
            logger.info(f"Creating ticket channel for {interaction.user.name} in category {category}")

            # Check if user already has an open ticket
            if await storage.has_open_ticket(str(interaction.user.id)):
                existing_channel_id = await storage.get_user_ticket_channel(str(interaction.user.id))

                if existing_channel_id:
                    try:
                        existing_channel = interaction.guild.get_channel(int(existing_channel_id))
                        if existing_channel:
                            # Extract ticket number from existing channel name
                            try:
                                existing_ticket_number = existing_channel.name.split('-')[1]
                                existing_ticket_data = await storage.get_ticket_log(existing_ticket_number)

                                # If the existing ticket's category is no longer active, allow new ticket creation
                                if existing_ticket_data and existing_ticket_data.get('category') not in self.active_categories:
                                    logger.info(f"User {interaction.user.name} has an inactive ticket open ({existing_ticket_data.get('category')}). Allowing new ticket creation.")
                                else:
                                    # Existing ticket is active, so block new creation
                                    await interaction.followup.send(
                                        embed=discord.Embed(
                                            title="❌ Existing Ticket",
                                            description=f"You already have an open ticket in {existing_channel.mention}. Please close your existing ticket before creating a new one.",
                                            color=discord.Color.red()
                                        ),
                                        ephemeral=True
                                    )
                                    return None
                            except (IndexError, TypeError):
                                logger.warning(f"Could not parse ticket number from existing channel name: {existing_channel.name}. Blocking new ticket creation to be safe.")
                                await interaction.followup.send(
                                    embed=discord.Embed(
                                        title="❌ Error",
                                        description="Could not determine existing ticket category. Please close your existing ticket or contact an administrator.",
                                        color=discord.Color.red()
                                    ),
                                    ephemeral=True
                                )
                                return None
                        else:
                            logger.info(f"User {interaction.user.name} has a ghost ticket entry. Proceeding with new ticket creation.")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error converting channel ID: {e}")
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="❌ Error",
                                description="An error occurred with your existing ticket. Please try again or contact an administrator.",
                                color=discord.Color.red()
                            ),
                            ephemeral=True
                        )
                        return None

            # Create category if it doesn't exist
            category_channel = discord.utils.get(interaction.guild.categories, name=category)
            if not category_channel:
                category_channel = await interaction.guild.create_category(category)
                logger.info(f"Created new category: {category}")

            # Generate ticket number
            ticket_number = await storage.get_next_ticket_number()
            if not ticket_number:
                logger.error("Failed to generate ticket number")
                await interaction.followup.send("Error creating ticket: Failed to generate ticket number", ephemeral=True)
                return None

            logger.info(f"Generated ticket number: {ticket_number}")

            # Get appropriate staff role for the category
            role_name = storage.get_category_role(category)
            staff_role = discord.utils.get(interaction.guild.roles, name=role_name) if role_name else None
            admin_role = discord.utils.get(interaction.guild.roles, name="Admin")

            # Set up channel name with the ticket number
            channel_name = f"ticket-{int(ticket_number):05d}"
            logger.info(f"Generated channel name: {channel_name}")

            # Set up channel permissions
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }

            # Add staff role permissions
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            # Create ticket channel
            ticket_channel = await category_channel.create_text_channel(
                name=channel_name,
                overwrites=overwrites
            )
            logger.info(f"Created ticket channel: {ticket_channel.name}")

            # Create combined welcome and ticket information embed
            if "Carry" in category:
                title = "🌟 Welcome to FakePixel Giveaways Carry Support! 🌟"
                greeting = (
                    f"Thank you for contacting us, {interaction.user.mention}! We're doing our best to help you.\n\n"
                    f"**Please note:** We know we're not always on time due to the high volume of carry requests. "
                    f"If you're waiting for our help for more than **2 hours**, don't be afraid to click on the "
                    f"**📞 Call for Help** button to receive priority assistance from our Staff faster.\n\n"
                    f"**Please do this instead of mentioning Staff directly, even if they're online.**"
                )
                color = discord.Color.blue()
            else:
                title = "🎫 Welcome to FakePixel Giveaways Support! 🎫"
                greeting = (
                    f"Thank you for contacting us, {interaction.user.mention}! We're here to help you.\n\n"
                    f"Our support team will assist you shortly. Please be patient while we review your request.\n\n"
                    f"If you need urgent assistance after waiting for a while, you can use the **📞 Call for Help** button below."
                )
                color = discord.Color.green()

            # Create the combined embed
            embed = discord.Embed(
                title=title,
                description=greeting,
                color=color,
                timestamp=datetime.utcnow()
            )

            # Add ticket information
            embed.add_field(
                name="🎫 Ticket Information",
                value=(
                    f"**Ticket #:** {ticket_number}\n"
                    f"**Category:** {category}\n"
                    f"**Status:** 🔄 Awaiting Response"
                ),
                inline=True
            )

            # Add helpful information
            embed.add_field(
                name="📋 What to expect:",
                value=(
                    "• Our team will respond as soon as possible\n"
                    "• Please provide all necessary details\n"
                    "• Be patient - quality service takes time!"
                ),
                inline=True
            )

            # Add service details if available
            if details:
                embed.add_field(
                    name="📝 Service Details",
                    value=details,
                    inline=False
                )

            # Add footer
            embed.set_footer(
                text="FakePixel Giveaways • Carry Services",
            )

            # Add thumbnail
            embed.set_thumbnail(url='https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo')

            # Set up controls with claim button
            controls = TicketControlsView(self.bot, ticket_number)
            control_message = await ticket_channel.send(
                embed=embed,
                view=controls
            )
            controls.message = control_message

            # Send ping to relevant role if it's a carry ticket
            if "Carry" in category:
                carrier_role_name = storage.get_category_role(category)
                if carrier_role_name:
                    carrier_role = discord.utils.get(interaction.guild.roles, name=carrier_role_name)
                    if carrier_role:
                        # Send a simple ping message without duplicating details
                        await ticket_channel.send(
                            content=f"{carrier_role.mention} A new **{category}** ticket has been created! Please claim it if you are available.",
                            allowed_mentions=discord.AllowedMentions(roles=True)
                        )
                        logger.info(f"Pinged {carrier_role.name} for new {category} ticket {ticket_number}")
                    else:
                        logger.warning(f"Carrier role '{carrier_role_name}' not found for guild {interaction.guild.name}")
                else:
                    logger.warning(f"No carrier role defined for category: {category}")

            # Store ticket information with creation time
            stored = await storage.create_ticket(
                ticket_number=ticket_number,
                user_id=str(interaction.user.id),
                channel_id=str(ticket_channel.id),
                category=category,
                details=details or "",
                guild_id=interaction.guild.id,
                control_message_id=control_message.id
            )
            
            if not stored:
                logger.error(f"Failed to store ticket {ticket_number}")
                await interaction.followup.send("❌ Failed to store ticket information.", ephemeral=True)
                return None
            
            # Set creation time
            await storage.update_ticket_times(ticket_number, "created", str(interaction.user.id))
            
            logger.info(f"[DEBUG] Ticket {ticket_number} stored with details: {details}")

            # Send confirmation
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✨ Ticket Created Successfully!",
                    description=f"Your ticket has been created in {ticket_channel.mention}\n\nOur team will assist you shortly!",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )

            logger.info(f"Ticket creation completed for user {interaction.user.name}")
            return ticket_channel

        except Exception as e:
            logger.error(f"Error creating ticket channel: {str(e)}")
            import traceback
            logger.error(f"Full error traceback: {traceback.format_exc()}")

            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description="An error occurred while creating the ticket. Please try again or contact an administrator.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return None

    async def on_message(self, message: discord.Message):
        """Handle messages in ticket channels"""
        try:
            # Ignore bot messages
            if message.author.bot:
                return

            # Check if message is in a ticket channel
            if not message.channel.name.startswith('ticket-'):
                return

            # Get ticket number from channel name
            try:
                ticket_number = message.channel.name.split('-')[1]
            except IndexError:
                return
            
            # Get ticket data
            ticket_data = await storage.get_ticket_log(ticket_number)
            if not ticket_data:
                return

            # Get required role based on category
            category = ticket_data.get('category')
            required_role = storage.get_category_role(category)
            
            if required_role and any(role.name == required_role for role in message.author.roles):
                # Update first response time if this is the first staff response
                await storage.update_ticket_times(ticket_number, "first_response", str(message.author.id))
                logger.info(f"Staff response recorded for ticket {ticket_number} by {message.author.name}")

        except Exception as e:
            logger.error(f"Error in on_message handler: {e}", exc_info=True)

    @app_commands.command(name="close_ticket")
    @app_commands.describe(reason="Reason for closing the ticket")
    async def close_ticket_command(self, interaction: discord.Interaction, reason: str = "Completed"):
        """Close a ticket (Staff only)"""
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

            # Check if this is a ticket channel
            if not interaction.channel.name.startswith('ticket-'):
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Invalid Channel",
                        description="This command can only be used in ticket channels.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            # Get ticket number
            try:
                ticket_number = interaction.channel.name.split('-')[1]
            except IndexError:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="Could not determine ticket number from channel name.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            # Get ticket data
            ticket_data = await storage.get_ticket_log(ticket_number)
            if not ticket_data:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="Ticket data not found.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            # Defer the response since closing might take some time
            await interaction.response.defer(ephemeral=True)

            try:
                # Update ticket times
                await storage.update_ticket_times(ticket_number, "resolved", str(interaction.user.id))
                
                # Close the ticket
                await storage.close_ticket(ticket_number, reason)
                
                # Send closing message
                await interaction.channel.send(
                    embed=discord.Embed(
                        title="🔒 Ticket Closing",
                        description=f"This ticket will be deleted in 10 seconds...\n\n**Close Reason:** {reason}\n**Closed by:** {interaction.user.mention}",
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
                        
                        # Create transcript
                        transcript_content = self.format_transcript(ticket_number, messages, ticket_data, reason, interaction.user)
                        
                        # Save transcript to file
                        import os
                        os.makedirs('transcripts', exist_ok=True)
                        transcript_file = f"transcripts/ticket_{ticket_number}.txt"
                        
                        with open(transcript_file, 'w', encoding='utf-8') as f:
                            f.write(transcript_content)
                        
                        # Send transcript to channel
                        with open(transcript_file, 'rb') as f:
                            file = discord.File(f, filename=f"ticket_{ticket_number}_transcript.txt")
                            
                            transcript_embed = discord.Embed(
                                title="📋 Ticket Transcript",
                                description=f"Transcript for ticket #{ticket_number}",
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
                                    f"**Close Reason:** {reason}"
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
                            from utils.views import StarRatingView
                            view = StarRatingView(ticket_number, int(creator_id))
                            
                            feedback_embed = discord.Embed(
                                title="🌟 Your Feedback Matters! Rate Your Service 🌟",
                                description=(
                                    f"Hello {creator.name}! Your ticket **#{ticket_number}** has been successfully closed.\n\n"
                                    "We hope you had a great experience with our support team. Your feedback helps us improve and provide even better service!\n\n"
                                    "Please take a moment to rate your overall experience below. It's quick, easy, and incredibly valuable to us!"
                                ),
                                color=discord.Color.from_rgb(255, 215, 0)
                            )
                            feedback_embed.add_field(
                                name="💡 Why Your Feedback is Important",
                                value="Your ratings and comments help us identify areas of improvement, recognize outstanding staff, and enhance our services for everyone.",
                                inline=False
                            )
                            feedback_embed.add_field(
                                name="✅ What Happens Next?",
                                value="Once you submit your rating, your feedback will be reviewed by our team. Thank you for helping us grow!",
                                inline=False
                            )
                            feedback_embed.set_footer(
                                text="FakePixel Giveaways • Customer Satisfaction Survey"
                            )
                            feedback_embed.set_thumbnail(url='https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo')
                            
                            try:
                                await creator.send(embed=feedback_embed, view=view)
                            except discord.Forbidden:
                                logger.warning(f"Could not send feedback request to {creator.name} - DMs closed")
                                
                except Exception as feedback_error:
                    logger.error(f"Error sending feedback request: {feedback_error}")
                
                # Store the ticket log with all messages
                await storage.store_ticket_log(
                    ticket_number=ticket_number,
                    messages=messages,
                    creator_id=ticket_data.get('creator_id'),
                    category=ticket_data.get('category'),
                    claimed_by=ticket_data.get('claimed_by'),
                    closed_by=str(interaction.user.id),
                    details=ticket_data.get('details'),
                    guild_id=interaction.guild.id,
                    close_reason=reason
                )
                
                # Wait before deleting
                await asyncio.sleep(10)
                
                # Delete the channel
                await interaction.channel.delete()
                
                logger.info(f"Ticket {ticket_number} closed successfully by {interaction.user.name}")
                
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
            logger.error(f"Error in close ticket command: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="An error occurred while trying to close the ticket.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )

    def format_transcript(self, ticket_number: str, messages: list, ticket_data: dict, close_reason: str, closed_by: discord.Member) -> str:
        """Format ticket messages into a readable transcript"""
        lines = []
        lines.append("=" * 70)
        lines.append("FAKEPIXEL GIVEAWAYS - TICKET TRANSCRIPT")
        lines.append("=" * 70)
        lines.append(f"TICKET NUMBER: #{ticket_number}")
        lines.append(f"CATEGORY: {ticket_data.get('category', 'Unknown')}")
        lines.append(f"CREATOR: {ticket_data.get('creator_id', 'Unknown')}")
        lines.append(f"CLAIMED BY: {ticket_data.get('claimed_by', 'Unclaimed')}")
        lines.append(f"CLOSED BY: {closed_by.name}")
        lines.append(f"CLOSE REASON: {close_reason}")
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

    @app_commands.command(name="ticket_stats")
    @app_commands.describe(ticket_number="The ticket number to get stats for")
    async def ticket_stats(self, interaction: discord.Interaction, ticket_number: str = None):
        """Get statistics for a specific ticket or general stats"""
        try:
            if not any(role.name in ["Staff", "Admin", "Moderator"] for role in interaction.user.roles):
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Permission Denied",
                        description="Only staff members can view ticket statistics.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            if ticket_number:
                # Get specific ticket stats
                ticket_data = await storage.get_ticket(ticket_number)
                if not ticket_data:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Ticket Not Found",
                            description=f"No ticket found with number {ticket_number}",
                            color=discord.Color.red()
                        ),
                        ephemeral=True
                    )
                    return

                embed = discord.Embed(
                    title=f"📊 Ticket #{ticket_number} Statistics",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )

                embed.add_field(
                    name="Basic Information",
                    value=(
                        f"**Category:** {ticket_data.get('category', 'Unknown')}\n"
                        f"**Status:** {ticket_data.get('status', 'Unknown')}\n"
                        f"**Claimed By:** {ticket_data.get('claimed_by', 'Unclaimed')}"
                    ),
                    inline=True
                )

                # Add timing information if available
                created_at = ticket_data.get('created_at')
                if created_at:
                    embed.add_field(
                        name="Timeline",
                        value=f"**Created:** <t:{int(discord.utils.parse_time(created_at).timestamp())}:R>",
                        inline=True
                    )

            else:
                # Get general statistics
                stats = await storage.get_ticket_statistics()
                
                embed = discord.Embed(
                    title="📊 General Ticket Statistics",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                
                embed.add_field(
                    name="Overall Stats",
                    value=(
                        f"**Total Tickets:** {stats.get('total_tickets', 0)}\n"
                        f"**Open Tickets:** {stats.get('open_tickets', 0)}\n"
                        f"**Closed Tickets:** {stats.get('closed_tickets', 0)}\n"
                        f"**Claimed Tickets:** {stats.get('claimed_tickets', 0)}"
                    ),
                    inline=True
                )
                
                if stats.get('categories'):
                    category_text = []
                    for category, cat_stats in stats['categories'].items():
                        category_text.append(f"**{category}:** {cat_stats['total']} total ({cat_stats['open']} open)")
                    
                    embed.add_field(
                        name="By Category",
                        value="\n".join(category_text[:5]),  # Limit to 5 categories
                        inline=True
                    )
                
                feedback_info = f"**Total Feedback:** {stats.get('total_feedback', 0)}"
                if stats.get('average_rating'):
                    feedback_info += f"\n**Average Rating:** {stats['average_rating']:.1f}/5.0"
                
                embed.add_field(
                    name="Feedback Stats",
                    value=feedback_info,
                    inline=True
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in ticket_stats command: {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="An error occurred while retrieving statistics.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(TicketCommands(bot))