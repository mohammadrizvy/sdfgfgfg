import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import storage
from datetime import datetime
from utils.database import DatabaseManager
from utils.transcript_manager import TranscriptManager
from utils.responses import create_embed
from utils.permissions import check_admin_permissions

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
            max_length=1
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
            placeholder="Enter floor (e.g., M1, M2, etc.)" if "Master" in category else "Enter floor (e.g., F1, F2, etc.)",
            required=True,
            max_length=2
        )
        self.completion = discord.ui.TextInput(
            label="Completion Type",
            placeholder="Enter S or S+",
            required=True,
        )
        self.carries = discord.ui.TextInput(
            label="Number of Carries",
            placeholder="How many carries do you need? (Max 9)",
            required=True,
            max_length=1
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

            # Validate floor based on category
            if self.category == "Normal Dungeon Carry" and not floor.startswith('F'):
                await interaction.followup.send(
                    "❌ For Normal Dungeon Carry, please use floors like F1, F2 (e.g., F1, F2, etc.).", 
                    ephemeral=True
                )
                return
            
            if self.category == "Master Dungeon Carry" and not floor.startswith('M'):
                await interaction.followup.send(
                    "❌ For Master Dungeon Carry, please use floors like M1, M2 (e.g., M1, M2, etc.).", 
                    ephemeral=True
                )
                return

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
        self.db = storage.get_db_manager()
        self.transcript_manager = TranscriptManager(bot)

    @app_commands.command(name="ticket_setup", description="Set up the ticket system in the current channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction):
        try:
            if not await check_admin_permissions(interaction):
                return

            embed = discord.Embed(
                title="🎫 Support Ticket System",
                description="Click the button below to create a new support ticket.",
                color=discord.Color.blue()
            )
            
            view = TicketControlsView(self.bot, None)
            await interaction.response.send_message(embed=embed, view=view)
            
            logger.info(f"Ticket system set up in channel {interaction.channel.name} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in ticket_setup: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while setting up the ticket system.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="close_ticket", description="Close the current ticket")
    @app_commands.checks.has_permissions(administrator=True)
    async def close_ticket(self, interaction: discord.Interaction):
        try:
            if not await check_admin_permissions(interaction):
                return

            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This command can only be used in ticket channels.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            ticket_number = channel_name.split("-")[1]
            
            await self.transcript_manager.create_transcript(interaction.channel, ticket_number)
            await interaction.channel.delete()
            
            logger.info(f"Ticket {ticket_number} closed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in close_ticket: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while closing the ticket.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="add_user", description="Add a user to the current ticket")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        try:
            if not await check_admin_permissions(interaction):
                return

            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This command can only be used in ticket channels.",
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
            
            logger.info(f"User {user.name} added to ticket {channel_name} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in add_user: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while adding the user.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="remove_user", description="Remove a user from the current ticket")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        try:
            if not await check_admin_permissions(interaction):
                return

            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This command can only be used in ticket channels.",
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
            
            logger.info(f"User {user.name} removed from ticket {channel_name} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in remove_user: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while removing the user.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="rename_ticket", description="Rename the current ticket")
    @app_commands.checks.has_permissions(administrator=True)
    async def rename_ticket(self, interaction: discord.Interaction, new_name: str):
        try:
            if not await check_admin_permissions(interaction):
                return

            channel_name = interaction.channel.name
            if not channel_name.startswith("ticket-"):
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "This command can only be used in ticket channels.",
                        "error"
                    ),
                    ephemeral=True
                )
                return

            ticket_number = channel_name.split("-")[1]
            new_channel_name = f"ticket-{ticket_number}-{new_name}"
            
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
            logger.error(f"Error in rename_ticket: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while renaming the ticket.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="ticket_stats", description="View ticket statistics")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_stats(self, interaction: discord.Interaction):
        try:
            if not await check_admin_permissions(interaction):
                return

            stats = await self.db.get_ticket_stats()
            
            embed = discord.Embed(
                title="📊 Ticket Statistics",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Total Tickets",
                value=str(stats.get('total_tickets', 0)),
                inline=True
            )
            embed.add_field(
                name="Open Tickets",
                value=str(stats.get('open_tickets', 0)),
                inline=True
            )
            embed.add_field(
                name="Closed Tickets",
                value=str(stats.get('closed_tickets', 0)),
                inline=True
            )
            
            await interaction.response.send_message(embed=embed)
            
            logger.info(f"Ticket stats viewed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in ticket_stats: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while fetching ticket statistics.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="purge_tickets", description="Delete all closed tickets")
    @app_commands.checks.has_permissions(administrator=True)
    async def purge_tickets(self, interaction: discord.Interaction):
        try:
            if not await check_admin_permissions(interaction):
                return

            closed_tickets = await self.db.get_all_closed_tickets()
            deleted_count = 0
            
            for ticket in closed_tickets:
                channel_id = ticket.get('channel_id')
                if channel_id:
                    try:
                        channel = self.bot.get_channel(int(channel_id))
                        if channel:
                            await channel.delete()
                            deleted_count += 1
                    except Exception as e:
                        logger.error(f"Error deleting channel {channel_id}: {e}")
            
            await interaction.response.send_message(
                embed=create_embed(
                    "Success",
                    f"Successfully deleted {deleted_count} closed tickets.",
                    "success"
                )
            )
            
            logger.info(f"Purged {deleted_count} closed tickets by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in purge_tickets: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while purging closed tickets.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="backup_tickets", description="Create a backup of all ticket data")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_tickets(self, interaction: discord.Interaction):
        try:
            if not await check_admin_permissions(interaction):
                return

            backup_path = await self.db.create_backup()
            
            if backup_path:
                await interaction.response.send_message(
                    embed=create_embed(
                        "Success",
                        f"Ticket backup created successfully at: {backup_path}",
                        "success"
                    )
                )
                
                logger.info(f"Ticket backup created by {interaction.user.name}")
            else:
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "Failed to create ticket backup.",
                        "error"
                    ),
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error in backup_tickets: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while creating the backup.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="restore_backup", description="Restore ticket data from a backup")
    @app_commands.checks.has_permissions(administrator=True)
    async def restore_backup(self, interaction: discord.Interaction, backup_file: str):
        try:
            if not await check_admin_permissions(interaction):
                return

            success = await self.db.restore_backup(backup_file)
            
            if success:
                await interaction.response.send_message(
                    embed=create_embed(
                        "Success",
                        "Ticket data restored successfully from backup.",
                        "success"
                    )
                )
                
                logger.info(f"Ticket data restored from backup by {interaction.user.name}")
            else:
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        "Failed to restore ticket data from backup.",
                        "error"
                    ),
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error in restore_backup: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while restoring the backup.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="ticket_logs", description="View recent ticket activity logs")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_logs(self, interaction: discord.Interaction, limit: int = 10):
        try:
            if not await check_admin_permissions(interaction):
                return

            logs = await self.db.get_recent_logs(limit)
            
            embed = discord.Embed(
                title="📝 Recent Ticket Activity",
                color=discord.Color.blue()
            )
            
            for log in logs:
                embed.add_field(
                    name=f"Ticket {log['ticket_number']}",
                    value=f"Action: {log['action']}\nUser: {log['user']}\nTime: {log['timestamp']}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
            logger.info(f"Ticket logs viewed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in ticket_logs: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while fetching ticket logs.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="ticket_settings", description="Configure ticket system settings")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_settings(self, interaction: discord.Interaction):
        try:
            if not await check_admin_permissions(interaction):
                return

            settings = await self.db.get_ticket_settings()
            
            embed = discord.Embed(
                title="⚙️ Ticket System Settings",
                color=discord.Color.blue()
            )
            
            for key, value in settings.items():
                embed.add_field(
                    name=key.replace('_', ' ').title(),
                    value=str(value),
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)
            
            logger.info(f"Ticket settings viewed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in ticket_settings: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while fetching ticket settings.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="update_settings", description="Update ticket system settings")
    @app_commands.checks.has_permissions(administrator=True)
    async def update_settings(self, interaction: discord.Interaction, setting: str, value: str):
        try:
            if not await check_admin_permissions(interaction):
                return

            success = await self.db.update_ticket_setting(setting, value)
            
            if success:
                await interaction.response.send_message(
                    embed=create_embed(
                        "Success",
                        f"Setting '{setting}' updated to '{value}'",
                        "success"
                    )
                )
                
                logger.info(f"Ticket setting '{setting}' updated to '{value}' by {interaction.user.name}")
            else:
                await interaction.response.send_message(
                    embed=create_embed(
                        "Error",
                        f"Failed to update setting '{setting}'",
                        "error"
                    ),
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error in update_settings: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while updating settings.",
                    "error"
                ),
                ephemeral=True
            )

    @app_commands.command(name="ticket_help", description="View ticket system help information")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_help(self, interaction: discord.Interaction):
        try:
            if not await check_admin_permissions(interaction):
                return

            embed = discord.Embed(
                title="📚 Ticket System Help",
                description="Here are the available ticket system commands:",
                color=discord.Color.blue()
            )
            
            commands = [
                ("/ticket_setup", "Set up the ticket system in the current channel"),
                ("/close_ticket", "Close the current ticket"),
                ("/add_user", "Add a user to the current ticket"),
                ("/remove_user", "Remove a user from the current ticket"),
                ("/rename_ticket", "Rename the current ticket"),
                ("/ticket_stats", "View ticket statistics"),
                ("/purge_tickets", "Delete all closed tickets"),
                ("/backup_tickets", "Create a backup of all ticket data"),
                ("/restore_backup", "Restore ticket data from a backup"),
                ("/ticket_logs", "View recent ticket activity logs"),
                ("/ticket_settings", "Configure ticket system settings"),
                ("/update_settings", "Update ticket system settings")
            ]
            
            for cmd, desc in commands:
                embed.add_field(name=cmd, value=desc, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
            logger.info(f"Ticket help viewed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error in ticket_help: {e}")
            await interaction.response.send_message(
                embed=create_embed(
                    "Error",
                    "An error occurred while fetching help information.",
                    "error"
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))