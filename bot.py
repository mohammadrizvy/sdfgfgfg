import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
import asyncio
from utils import storage
from utils.views import TicketControlsView
from utils.database import DatabaseManager
from utils.config import MONGODB_URI, DATABASE_NAME

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Load environment variables
load_dotenv()

# Define required channels and their descriptions
REQUIRED_CHANNELS = {
    'ticket-transcripts': {
        'description': 'Channel for storing ticket transcripts',
        'permissions': lambda guild: {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
    },
    'feedback-logs': {
        'description': 'Channel for ticket feedback logs',
        'permissions': lambda guild: {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
    },
    'priority-alerts': {
        'description': 'Channel for high priority ticket alerts',
        'permissions': lambda guild: {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
    }
}

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

async def setup_commands():
    """Load and register bot commands"""
    try:
        # Import command modules
        from commands.admin import AdminCommands
        from commands.tickets import TicketCommands
        
        # Add cogs to bot
        await bot.add_cog(AdminCommands(bot))
        await bot.add_cog(TicketCommands(bot))
        
        # Sync command tree
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
            logger.info(f"Commands synced for guild: {guild.name}")
            # Log the commands registered for each guild
            guild_commands = await bot.tree.fetch_commands(guild=guild)
            command_names = [cmd.name for cmd in guild_commands]
            logger.info(f"Registered commands for {guild.name}: {', '.join(command_names)}")

        logger.info("Commands registered and synced successfully")
        
    except Exception as e:
        logger.error(f"Error setting up commands: {e}")
        # Don't raise - let bot continue without commands for debugging

async def setup_required_channels(guild: discord.Guild):
    """Create required channels if they don't exist"""
    try:
        created_channels = []
        for channel_name, config in REQUIRED_CHANNELS.items():
            # Check if channel already exists
            channel = discord.utils.get(guild.channels, name=channel_name)
            if not channel:
                # Create channel with proper permissions
                overwrites = config['permissions'](guild)
                channel = await guild.create_text_channel(
                    name=channel_name,
                    topic=config['description'],
                    overwrites=overwrites
                )
                created_channels.append(channel_name)
                logger.info(f"Created {channel_name} channel in {guild.name}")
            else:
                logger.info(f"Channel {channel_name} already exists in {guild.name}")
        
        if created_channels:
            logger.info(f"Successfully created channels: {', '.join(created_channels)}")
            
    except Exception as e:
        logger.error(f"Error setting up required channels: {e}")

@bot.event
async def on_ready():
    try:
        logger.info(f'Bot is ready: {bot.user.name} (ID: {bot.user.id})')
        logger.info(f'Connected to {len(bot.guilds)} guilds')
        
        # Initialize database manager and connect
        bot.db = DatabaseManager()
        await bot.db.connect() # Ensure connection is established
        storage.set_db_manager(bot.db) # Set the database manager in the storage module
        
        # Register persistent views for existing tickets
        logger.info("Registering persistent views...")
        open_tickets = await bot.db.get_all_open_tickets()
        for ticket in open_tickets:
            ticket_number = ticket.get('ticket_number')
            channel_id = ticket.get('channel_id')
            control_message_id = ticket.get('control_message_id')

            if ticket_number and channel_id and control_message_id:
                try:
                    channel = bot.get_channel(int(channel_id))
                    if not channel: # Channel might have been deleted
                        channel = await bot.fetch_channel(int(channel_id))

                    if channel and isinstance(channel, discord.TextChannel):
                        message = await channel.fetch_message(int(control_message_id))
                        if message:
                            view = TicketControlsView(bot, ticket_number)
                            bot.add_view(view) # Re-add the view for persistence
                            view.message = message # Set the message for the view
                            await message.edit(view=view) # Explicitly edit the message to apply the view
                            logger.info(f"Registered and updated persistent view for ticket {ticket_number} in channel {channel_id}")
                        else:
                            logger.warning(f"Control message {control_message_id} not found for ticket {ticket_number}.")
                    else:
                        logger.warning(f"Channel {channel_id} not found or not a text channel for ticket {ticket_number}.")
                except discord.NotFound:
                    logger.warning(f"Channel or message for ticket {ticket_number} not found (Discord.NotFound). Skipping persistent view registration.")
                except Exception as e:
                    logger.error(f"Error fetching/updating message for persistent view ticket {ticket_number}: {e}")

        # Set up commands
        await setup_commands()
        
        # Set up required channels for each guild
        for guild in bot.guilds:
            logger.info(f"Setting up channels for guild: {guild.name}")
            await setup_required_channels(guild)
            
        logger.info("Bot setup complete - All channels and commands ready!")
        
        # Set bot status
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for tickets | /ticket_setup"
            )
        )
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")

@bot.event
async def on_guild_join(guild):
    """Set up channels when bot joins a new guild"""
    try:
        logger.info(f"Joined new guild: {guild.name}")
        await setup_required_channels(guild)
    except Exception as e:
        logger.error(f"Error setting up channels for new guild {guild.name}: {e}")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    try:
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=discord.Embed(
                    title="❌ Missing Permissions",
                    description="You don't have permission to use this command!",
                    color=discord.Color.red()
                )
            )
        elif isinstance(error, commands.CommandNotFound):
            await ctx.send(
                embed=discord.Embed(
                    title="❌ Command Not Found",
                    description="That command doesn't exist!",
                    color=discord.Color.red()
                )
            )
        else:
            logger.error(f"Command error: {str(error)}")
            await ctx.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred: {str(error)}",
                    color=discord.Color.red()
                )
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

# Get token from environment variables
token = os.getenv('DISCORD_TOKEN')
if not token:
    logger.error("No Discord token found in environment variables. Please set DISCORD_TOKEN in .env file")
    print("Please add your Discord bot token to the .env file")
    exit(1)

# Run the bot
if __name__ == "__main__":
    try:
        # Ensure data directories exist
        os.makedirs('transcripts', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)
        
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        exit(1)