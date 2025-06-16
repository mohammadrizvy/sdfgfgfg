import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import storage
from datetime import datetime

logger = logging.getLogger('discord')

class TicketCategorySelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Slayer Carry",
                description="Get help with any slayer task",
                emoji="⚔️"
            ),
            discord.SelectOption(
                label="Normal Dungeon Carry",
                description="Complete any normal dungeon",
                emoji="🏰"
            ),
            discord.SelectOption(
                label="Master Dungeon Carry",
                description="Master dungeon completion",
                emoji="👑"
            ),
        ]
        super().__init__(
            placeholder="Select a service...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_category = self.values[0]
            logger.info(f"Selected category: {selected_category}")

            if selected_category == "Slayer Carry":
                modal = SlayerCarryModal(self.bot)
            else:
                modal = CarryRequestModal(self.bot, selected_category)

            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error in ticket creation callback: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Error",
                            description="An error occurred while creating the ticket.",
                            color=discord.Color.red()
                        ),
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="❌ Error",
                            description="An error occurred while creating the ticket.",
                            color=discord.Color.red()
                        ),
                        ephemeral=True
                    )
            except Exception as followup_error:
                logger.error(f"Error sending error message: {followup_error}")

class SlayerCarryModal(discord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Slayer Carry Request")
        self.bot = bot
        
        self.in_game_name = discord.ui.TextInput(
            label="In-Game Name",
            placeholder="Your in-game username",
            required=True,
            max_length=50
        )
        self.slayer_type = discord.ui.TextInput(
            label="Slayer Type",
            placeholder="Which slayer boss? (e.g., Revenant, Zombie, Spider, Wolf)",
            required=True,
            max_length=50
        )
        self.tier = discord.ui.TextInput(
            label="Tier",
            placeholder="Which tier? (e.g., T1, T2, T3, T4, T5)",
            required=True,
            max_length=2
        )
        self.carries = discord.ui.TextInput(
            label="Number of Carries",
            placeholder="How many slayer boss carries do you need?",
            required=True,
            max_length=5
        )
        
        for field in [self.in_game_name, self.slayer_type, self.tier, self.carries]:
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Defer the response immediately
            await interaction.response.defer(ephemeral=True)
            
            carry_details = (
                f"**In-Game Name:** {self.in_game_name.value}\n"
                f"**Slayer Type:** {self.slayer_type.value}\n"
                f"**Tier:** {self.tier.value}\n"
                f"**Number of Carries:** {self.carries.value}"
            )

            ticket_commands = self.bot.get_cog('TicketCommands')
            if ticket_commands:
                await interaction.followup.send("✅ Your slayer carry request has been submitted!", ephemeral=True)
                await ticket_commands.create_ticket_channel(interaction, "Slayer Carry", carry_details)
            else:
                logger.error("TicketCommands cog not found")
                await interaction.followup.send(
                    "An error occurred while creating the ticket.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in slayer carry submission: {e}")
            try:
                await interaction.followup.send(
                    "An error occurred while creating the ticket.",
                    ephemeral=True
                )
            except:
                pass

class CarryRequestModal(discord.ui.Modal):
    def __init__(self, bot, category):
        super().__init__(title="Carry Request")
        self.bot = bot
        self.category = category
        
        self.in_game_name = discord.ui.TextInput(
            label="In-Game Name",
            placeholder="Your in-game username",
            required=True,
            max_length=50
        )
        self.floor = discord.ui.TextInput(
            label="Floor",
            placeholder="Enter floor (e.g., F1, F2, etc.)",
            required=True,
            max_length=2
        )
        self.completion = discord.ui.TextInput(
            label="Completion Type",
            placeholder="Enter S or S+",
            required=True,
            max_length=2
        )
        self.carries = discord.ui.TextInput(
            label="Number of Carries",
            placeholder="How many carries do you need? (Max 3 for master)",
            required=True,
            max_length=3
        )
        
        for field in [self.in_game_name, self.floor, self.completion, self.carries]:
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Defer the response immediately
            await interaction.response.defer(ephemeral=True)
            
            in_game_name = self.in_game_name.value
            floor = self.floor.value.upper()
            completion = self.completion.value.upper()
            carries = self.carries.value

            carry_details = (
                f"**In-Game Name:** {in_game_name}\n"
                f"**Floor:** {floor}\n"
                f"**Completion Type:** {completion}\n"
                f"**Number of Carries:** {carries}"
            )

            ticket_commands = self.bot.get_cog('TicketCommands')
            if ticket_commands:
                await interaction.followup.send("✅ Your carry request has been submitted!", ephemeral=True)
                await ticket_commands.create_ticket_channel(interaction, self.category, carry_details)
            else:
                logger.error("TicketCommands cog not found")
                await interaction.followup.send(
                    "An error occurred while creating the ticket.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in carry request submission: {e}")
            try:
                await interaction.followup.send(
                    "An error occurred while creating the ticket.",
                    ephemeral=True
                )
            except:
                pass

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket_setup")
    @app_commands.describe(channel="The channel where the ticket panel will be created")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set up the ticket system in a specific channel"""
        try:
            # Respond immediately to prevent timeout
            await interaction.response.defer(ephemeral=True)
            
            logger.info(f"Setting up ticket system in channel: {channel.name}")

            # Delete existing messages in the channel
            try:
                deleted_count = 0
                async for message in channel.history(limit=100):
                    if message.author == self.bot.user:
                        await message.delete()
                        deleted_count += 1
                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} existing ticket panel messages")
            except Exception as e:
                logger.error(f"Error deleting old messages: {e}")

            embed = discord.Embed(
                title="🎫 Ticket System",
                description=(
                    "Welcome to our ticket system! Please select a category below to create a ticket.\n\n"
                    "⚔️ **Slayer Carry**\n"
                    "• Get help with any slayer task\n"
                    "• Professional slayer assistance\n"
                    "• Fast and efficient service\n\n"
                    "🏰 **Normal Dungeon Carry**\n"
                    "• Complete any normal dungeon\n"
                    "• Expert guidance\n"
                    "• Guaranteed completion\n\n"
                    "👑 **Master Dungeon Carry**\n"
                    "• High-level dungeon experts\n"
                    "• Efficient completion times\n"
                ),
                color=discord.Color.blue()
            )

            # Add footer
            embed.set_footer(
                text="fakepixle giveaways • Carry Services",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )

            # Add thumbnail
            embed.set_thumbnail(url='https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo')

            # Create view with category select
            view = discord.ui.View(timeout=None)  # Persistent view
            view.add_item(TicketCategorySelect(self.bot))

            # Send the embed with the view
            await channel.send(embed=embed, view=view)
            
            # Send success response
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Ticket System Setup Complete",
                    description=f"Ticket system has been set up in {channel.mention}",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
            logger.info(f"Ticket system setup completed in channel: {channel.name}")

        except Exception as e:
            logger.error(f"Error setting up ticket system: {e}")
            try:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="An error occurred while setting up the ticket system.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
            except Exception as followup_error:
                logger.error(f"Error sending followup message: {followup_error}")

    @app_commands.command(name="add_user")
    @app_commands.describe(user="The user to add", role="The role to assign (staff, carrier, moderator)")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_user(self, interaction: discord.Interaction, user: discord.Member, role: str):
        """Add a user to the system with a specific role"""
        try:
            # Respond immediately
            await interaction.response.defer(ephemeral=True)
            
            # Validate role
            valid_roles = ["staff", "carrier", "moderator"]
            if role.lower() not in valid_roles:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Invalid Role",
                        description=f"Please specify one of these roles: {', '.join(valid_roles)}",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            # Create user data
            user_data = {
                "user_id": str(user.id),
                "username": user.name,
                "role": role.lower(),
                "added_by": str(interaction.user.id),
                "added_at": discord.utils.utcnow().isoformat(),
                "status": "active"
            }

            # Store user data
            if storage.add_user(user_data):
                # Create success embed
                embed = discord.Embed(
                    title="✅ User Added Successfully",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="User Information",
                    value=(
                        f"**User:** {user.mention}\n"
                        f"**Role:** {role.capitalize()}\n"
                        f"**Added by:** {interaction.user.mention}\n"
                        f"**Status:** Active"
                    ),
                    inline=False
                )
                embed.set_footer(text=f"User ID: {user.id}")

                await interaction.followup.send(embed=embed)
                logger.info(f"User {user.name} (ID: {user.id}) added with role: {role}")
            else:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="Failed to add user. Please try again.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in add_user command: {e}")
            try:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="An error occurred while adding the user.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
            except:
                pass

    @app_commands.command(name="transcript_stats")
    @app_commands.checks.has_permissions(administrator=True)
    async def transcript_stats(self, interaction: discord.Interaction):
        """View transcript system statistics (Admin only)"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get transcript statistics
            stats = await interaction.client.transcript_manager.get_transcript_stats()
            
            embed = discord.Embed(
                title="📊 Transcript System Statistics",
                description="Overview of the enhanced transcript system",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="📋 Generated Transcripts",
                value=(
                    f"**HTML Transcripts:** {stats.get('total_html_transcripts', 0)}\n"
                    f"**Text Backups:** {stats.get('total_text_transcripts', 0)}\n"
                    f"**Storage Used:** {stats.get('storage_used', 'Unknown')}"
                ),
                inline=True
            )
            
            embed.add_field(
                name="⏰ Recent Activity",
                value=(
                    f"**Last Generated:** {stats.get('last_generated', 'Never')[:19] if stats.get('last_generated') else 'Never'}\n"
                    f"**System Status:** ✅ Operational\n"
                    f"**HTML Generator:** ✅ Active"
                ),
                inline=True
            )
            
            embed.add_field(
                name="🔧 Maintenance",
                value=(
                    "Use `/cleanup_transcripts` to clean old files\n"
                    "HTML transcripts provide the best experience\n"
                    "Text backups ensure data preservation"
                ),
                inline=False
            )
            
            embed.set_footer(
                text="fakepixle giveaways • Enhanced Transcript System",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in transcript_stats command: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description="Failed to retrieve transcript statistics.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

    @app_commands.command(name="cleanup_transcripts")
    @app_commands.describe(days="Number of days to keep transcripts (default: 30)")
    @app_commands.checks.has_permissions(administrator=True)
    async def cleanup_transcripts(self, interaction: discord.Interaction, days: int = 30):
        """Clean up old transcript files (Admin only)"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            if days < 1:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Invalid Input",
                        description="Days must be at least 1.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return
            
            # Cleanup old transcripts
            deleted_count = await interaction.client.transcript_manager.cleanup_old_transcripts(days)
            
            embed = discord.Embed(
                title="🧹 Transcript Cleanup Complete",
                description=f"Successfully cleaned up old transcript files",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="📊 Cleanup Results",
                value=(
                    f"**Files Deleted:** {deleted_count}\n"
                    f"**Retention Period:** {days} days\n"
                    f"**Status:** ✅ Complete"
                ),
                inline=False
            )
            
            embed.set_footer(
                text="fakepixle giveaways • Transcript Maintenance",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Transcript cleanup completed by {interaction.user.name}: {deleted_count} files deleted")
            
        except Exception as e:
            logger.error(f"Error in cleanup_transcripts command: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description="Failed to cleanup transcript files.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))