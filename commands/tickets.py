import discord
from discord.ext import commands
from discord import app_commands
from utils import permissions, storage, responses
from utils.ticket_closing import TicketClosingSystem
from utils.views import TicketControlsView, StarRatingView, FeedbackModal, FeedbackDisplayView
import logging
import asyncio
from typing import Optional, List
import io
from datetime import datetime, timezone

logger = logging.getLogger('discord')

class TicketCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_categories = ['Slayer Carry', 'Normal Dungeon Carry', 'Master Dungeon Carry']
        logger.info("TicketCommands cog initialized")
        
        # Add message event listener
        self.bot.add_listener(self.on_message, 'on_message')

    async def create_ticket_channel(self, interaction: discord.Interaction, category: str, details: Optional[str] = None):
        try:
            logger.info(f"Creating ticket channel for {interaction.user.name} in category {category} with details: {details}")

            if storage.has_open_ticket(str(interaction.user.id)):
                existing_channel_id = storage.get_user_ticket_channel(str(interaction.user.id))

                # Guard against None and invalid channel ID
                if existing_channel_id:
                    try:
                        existing_channel = interaction.guild.get_channel(int(existing_channel_id))
                        if existing_channel:
                            await interaction.followup.send(
                                embed=discord.Embed(
                                    title="❌ Existing Ticket",
                                    description=f"You already have an open ticket in {existing_channel.mention}. Please close your existing ticket before creating a new one.",
                                    color=discord.Color.red()
                                ),
                                ephemeral=True
                            )
                            return None
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error converting channel ID: {e}")

            # Create category if it doesn't exist
            category_channel = discord.utils.get(interaction.guild.categories, name=category)
            if not category_channel:
                category_channel = await interaction.guild.create_category(category)
                logger.info(f"Created new category: {category}")

            # Generate ticket number
            ticket_number = str(storage.get_next_ticket_number() or "ERROR")
            if ticket_number == "ERROR":
                logger.error("Failed to generate ticket number")
                await interaction.followup.send("Error creating ticket: Failed to generate ticket number", ephemeral=True)
                return None

            logger.info(f"Generated ticket number: {ticket_number}")

            # Get appropriate staff role for the category
            role_name = storage.get_category_role(category)
            staff_role = discord.utils.get(interaction.guild.roles, name=role_name) if role_name else None
            admin_role = discord.utils.get(interaction.guild.roles, name="Admin")

            # Set up channel name with just the padded ticket number
            channel_name = f"ticket-{int(ticket_number):04d}"
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
                inline=False
            )

            # Add service details if available
            if details:
                embed.add_field(
                    name="📝 Service Details",
                    value=f"```{details}```",
                    inline=False
                )

            # Add footer
            embed.set_footer(
                text="FakePixel Giveaways • Carry Services",
                icon_url=None
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
                        await ticket_channel.send(
                            content=f"{carrier_role.mention} A new **{category}** ticket has been created! Please claim it if you are available.\n\n**Details:** {details or 'No additional details provided.'}",
                            allowed_mentions=discord.AllowedMentions(roles=True)
                        )
                        logger.info(f"Pinged {carrier_role.name} for new {category} ticket {ticket_number}")
                    else:
                        logger.warning(f"Carrier role '{carrier_role_name}' not found for guild {interaction.guild.name}")
                else:
                    logger.warning(f"No carrier role defined for category: {category}")

            # Store ticket information with creation time
            stored = storage.create_ticket(
                ticket_number=ticket_number,
                user_id=str(interaction.user.id),
                channel_id=str(ticket_channel.id),
                category=category,
                details=details or "",
                guild_id=interaction.guild.id
            )
            
            # Set creation time
            storage.update_ticket_times(ticket_number, "created", str(interaction.user.id))
            
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

    async def create_welcome_message(self, channel: discord.TextChannel, category: str, user: discord.Member) -> None:
        """Create and send the welcome message for the ticket"""
        try:
            # Create the greeting embed based on category
            if "Carry" in category:
                title = "🌟 Welcome to FakePixel Giveaways Carry Support! 🌟"
                greeting = (
                    f"Thank you for contacting us, {user.mention}! We're doing our best to help you.\n\n"
                    f"**Please note:** We know we're not always on time due to the high volume of carry requests. "
                    f"If you're waiting for our help for more than **2 hours**, don't be afraid to click on the "
                    f"**📞 Call for Help** button to receive priority assistance from our Staff faster.\n\n"
                    f"**Please do this instead of mentioning Staff directly, even if they're online.**"
                )
                color = discord.Color.blue()
            else:
                title = "🎫 Welcome to FakePixel Giveaways Support! 🎫"
                greeting = (
                    f"Thank you for contacting us, {user.mention}! We're here to help you.\n\n"
                    f"Our support team will assist you shortly. Please be patient while we review your request.\n\n"
                    f"If you need urgent assistance after waiting for a while, you can use the **📞 Call for Help** button below."
                )
                color = discord.Color.green()

            # Create the welcome embed
            welcome_embed = discord.Embed(
                title=title,
                description=greeting,
                color=color,
                timestamp=datetime.utcnow()
            )

            # Add helpful information
            welcome_embed.add_field(
                name="📋 What to expect:",
                value=(
                    "• Our team will respond as soon as possible\n"
                    "• Please provide all necessary details\n"
                    "• Be patient - quality service takes time!"
                ),
                inline=False
            )

            # Add footer
            welcome_embed.set_footer(
                     text="FakePixel Giveaways • Carry Services" if "Carry" in category else "FakePixel Giveaways • Support Services",
                icon_url=None
            )

            # Add thumbnail
            welcome_embed.set_thumbnail(url='https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo')

            # Send the welcome message
            await channel.send(embed=welcome_embed)
            logger.info(f"Welcome message sent to channel {channel.name}")

        except Exception as e:
            logger.error(f"Error creating welcome message: {e}")

    async def on_message(self, message: discord.Message):
        try:
            # Ignore bot messages
            if message.author.bot:
                return

            # Check if message is in a ticket channel
            if not message.channel.name.startswith('ticket-'):
                return

            # Get ticket number from channel name
            ticket_number = message.channel.name.split('-')[1]
            
            # Get ticket data
            ticket_data = storage.get_ticket_log(ticket_number)
            if not ticket_data:
                return

            # Get required role based on category
            category = ticket_data.get('category')
            required_role = storage.get_category_role(category)
            
            if required_role and any(role.name == required_role for role in message.author.roles):
                logger.info(f"Staff response recorded for ticket {ticket_number} by {message.author.name}")

        except Exception as e:
            logger.error(f"Error in on_message handler: {e}", exc_info=True)

async def setup(bot):
    await bot.add_cog(TicketCommands(bot))