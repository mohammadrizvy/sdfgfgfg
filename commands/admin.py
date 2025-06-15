import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import storage

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

            if selected_category == "Staff Application":
                modal = StaffApplicationModal(self.bot)
            elif selected_category == "Slayer Carry":
                modal = SlayerCarryModal(self.bot)
            else:
                modal = CarryRequestModal(self.bot)

            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error in ticket creation callback: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description="An error occurred while creating the ticket.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

class StaffApplicationModal(discord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Staff Application")
        self.bot = bot
        self.in_game_name = discord.ui.TextInput(
            label="In-Game Name",
            placeholder="Your in-game username",
            required=True,
            max_length=50
        )
        self.name = discord.ui.TextInput(
            label="Full Name",
            placeholder="Your full name (letters only)",
            required=True,
            max_length=50
        )
        self.age = discord.ui.TextInput(
            label="Age",
            placeholder="Your age (numbers only)",
            required=True,
            max_length=2
        )
        self.availability = discord.ui.TextInput(
            label="Country and Available Hours",
            placeholder="Your country and available hours per day",
            required=True,
            max_length=100
        )
        self.experience = discord.ui.TextInput(
            label="Previous Experience",
            placeholder="Describe your relevant experience",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        self.additional_info = discord.ui.TextInput(
            label="Additional Information",
            placeholder="Anything else you'd like to share",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        for field in [self.in_game_name, self.name, self.age, self.availability, self.experience, self.additional_info]:
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate age is numeric
            if not self.age.value.isdigit():
                await interaction.response.send_message("Age must be a number.", ephemeral=True)
                return

            # Validate name contains only letters and spaces
            if not all(c.isalpha() or c.isspace() for c in self.name.value):
                await interaction.response.send_message("Name must contain only letters.", ephemeral=True)
                return

            application_details = (
                f"**In-Game Name:** {self.in_game_name.value}\n"
                f"**Name:** {self.name.value}\n"
                f"**Age:** {self.age.value}\n"
                f"**Country and Available Hours:** {self.availability.value}\n"
                f"**Previous Experience:** {self.experience.value}\n"
                f"**Additional Information:** {self.additional_info.value or 'None provided'}"
            )

            ticket_commands = self.bot.get_cog('TicketCommands')
            if ticket_commands:
                await interaction.response.send_message(storage.get_confirmation_message(), ephemeral=True)
                await ticket_commands.create_ticket_channel(interaction, "Staff Applications", application_details)
            else:
                logger.error("TicketCommands cog not found")
                await interaction.response.send_message(
                    "An error occurred while creating the application.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in staff application submission: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while creating the application.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred while creating the application.",
                    ephemeral=True
                )

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
            # Validate tier format
            if not self.tier.value.upper().startswith('T') or not self.tier.value[1:].isdigit():
                await interaction.response.send_message(
                    "Invalid tier format. Please use T1, T2, T3, T4, or T5.",
                    ephemeral=True
                )
                return

            # Validate carries is a number
            if not self.carries.value.isdigit():
                await interaction.response.send_message(
                    "Number of carries must be a positive number.",
                    ephemeral=True
                )
                return

            carry_details = (
                f"**In-Game Name:** {self.in_game_name.value}\n"
                f"**Slayer Type:** {self.slayer_type.value}\n"
                f"**Tier:** {self.tier.value.upper()}\n"
                f"**Number of Carries:** {self.carries.value}"
            )

            ticket_commands = self.bot.get_cog('TicketCommands')
            if ticket_commands:
                await interaction.response.send_message(storage.get_confirmation_message(), ephemeral=True)
                await ticket_commands.create_ticket_channel(interaction, "Slayer Carry", carry_details)
            else:
                logger.error("TicketCommands cog not found")
                await interaction.response.send_message(
                    "An error occurred while creating the ticket.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in slayer carry submission: {e}")
            await interaction.response.send_message(
                "An error occurred while creating the ticket.",
                ephemeral=True
            )

class CarryRequestModal(discord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Carry Request")
        self.bot = bot
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
            in_game_name = self.in_game_name.value
            floor = self.floor.value.upper()
            completion = self.completion.value.upper()
            carries = self.carries.value

            # Validate floor format
            if not floor.startswith('F') or not floor[1:].isdigit() or int(floor[1:]) < 1 or int(floor[1:]) > 7:
                await interaction.response.send_message(
                    "Invalid floor format. Please use F1, F2, F3, F4, F5, F6, or F7.",
                    ephemeral=True
                )
                return

            # Validate completion type
            if completion not in ['S', 'S+']:
                await interaction.response.send_message(
                    "Invalid completion type. Please specify either S or S+.",
                    ephemeral=True
                )
                return

            # Validate carries is a number and within limits
            if not carries.isdigit():
                await interaction.response.send_message(
                    "Number of carries must be a positive number.",
                    ephemeral=True
                )
                return

            # Check if it's a master floor (F6 or F7)
            is_master_floor = floor in ['F6', 'F7']
            
            # Validate carries limit based on floor type
            carries_num = int(carries)
            if is_master_floor:
                if carries_num > 3:
                    await interaction.response.send_message(
                        "For master floors (F6, F7), the maximum number of carries is 3.",
                        ephemeral=True
                    )
                    return
            elif carries_num > 10:  # Regular floors can have more carries
                await interaction.response.send_message(
                    "The maximum number of carries for regular floors is 10.",
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
                await interaction.response.send_message(storage.get_confirmation_message(), ephemeral=True)
                await ticket_commands.create_ticket_channel(interaction, "Carry Request", carry_details)
            else:
                logger.error("TicketCommands cog not found")
                await interaction.response.send_message(
                    "An error occurred while creating the ticket.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in carry request submission: {e}")
            await interaction.response.send_message(
                "An error occurred while creating the ticket.",
                ephemeral=True
            )

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket_setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set up the ticket system in a specific channel"""
        try:
            logger.info(f"Setting up ticket system in channel: {channel.name}")

            # Delete existing messages in the channel
            try:
                async for message in channel.history(limit=100):
                    if message.author == self.bot.user:
                        await message.delete()
                logger.info("Deleted existing ticket panel messages")
            except Exception as e:
                logger.error(f"Error deleting old messages: {e}")

            embed = discord.Embed(
                title="🎮 Carry Service",
                description=(
                    "Welcome to our carry service! Choose a service below to create a ticket.\n\n"
                    "**Available Services:**\n\n"
                    "⚔️ **Slayer Carry**\n"
                    "• Get help with any slayer task\n"
                    "• Fast and efficient completion\n"
                    "• Experienced slayers available\n\n"
                    "🏰 **Normal Dungeon Carry**\n"
                    "• Complete any normal dungeon\n"
                    "• Safe and reliable runs\n"
                    "• Experienced dungeoneers\n\n"
                    "👑 **Master Dungeon Carry**\n"
                    "• Master dungeon completion\n"
                    "• High-level dungeon experts\n"
                    "• Efficient completion times"
                ),
                color=discord.Color.blue()
            )

            # Add footer
            embed.set_footer(
                text="FakePixel Giveaways • Carry Services",
                icon_url=None
            )

            # Add thumbnail
            embed.set_thumbnail(url='https://drive.google.com/uc?export=view&id=17DOuf9x93haDT9sB-KlSgWgaRJdLQWfo')

            # Create view with category select
            view = discord.ui.View(timeout=86400)  # Set 24 hour timeout for the view
            view.add_item(TicketCategorySelect(self.bot))

            # Send the embed with the view
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(
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
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="An error occurred while setting up the ticket system.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

    @app_commands.command(name="add_user")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_user(self, interaction: discord.Interaction, user: discord.Member, role: str):
        """Add a user to the system with a specific role"""
        try:
            # Validate role
            valid_roles = ["staff", "carrier", "moderator"]
            if role.lower() not in valid_roles:
                await interaction.response.send_message(
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

                await interaction.response.send_message(embed=embed)
                logger.info(f"User {user.name} (ID: {user.id}) added with role: {role}")
            else:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="Failed to add user. Please try again.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in add_user command: {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="An error occurred while adding the user.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))