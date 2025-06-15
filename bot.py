import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
from commands import admin, tickets
from utils import permissions, storage, responses

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Define required channels and their descriptions
REQUIRED_CHANNELS = {
    'transcript': {
        'name': 'ticket-transcripts',
        'description': 'Channel for storing ticket transcripts',
        'permissions': lambda guild: {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
    },
    'feedback-logs': {
        'name': 'feedback-logs',
        'description': 'Channel for ticket feedback logs',
        'permissions': lambda guild: {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
    },
    'priority-alerts': {
        'name': 'priority-alerts',
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

# Register commands
async def setup_commands():
    try:
        # Create instances of command cogs
        admin_commands = admin.AdminCommands(bot)
        ticket_commands = tickets.TicketCommands(bot)

        # Add cogs to bot
        await bot.add_cog(admin_commands)
        await bot.add_cog(ticket_commands)

        # Sync command tree
        await bot.tree.sync()

        logger.info("Commands registered and synced successfully")
    except Exception as e:
        logger.error(f"Error setting up commands: {e}")
        raise

async def setup_required_channels(guild: discord.Guild):
    """Create required channels if they don't exist"""
    try:
        created_channels = []
        for channel_type, config in REQUIRED_CHANNELS.items():
            # Check if channel already exists
            channel = discord.utils.get(guild.channels, name=config['name'])
            if not channel:
                # Create channel with proper permissions
                overwrites = config['permissions'](guild)
                channel = await guild.create_text_channel(
                    name=config['name'],
                    topic=config['description'],
                    overwrites=overwrites
                )
                created_channels.append(config['name'])
                logger.info(f"Created {config['name']} channel in {guild.name}")
            else:
                logger.info(f"Channel {config['name']} already exists in {guild.name}")
        
        if created_channels:
            logger.info(f"Successfully created channels: {', '.join(created_channels)}")
            
    except Exception as e:
        logger.error(f"Error setting up required channels: {e}")

@bot.event
async def on_ready():
    try:
        logger.info(f'Bot is ready: {bot.user.name} (ID: {bot.user.id})')
        logger.info(f'Connected to {len(bot.guilds)} guilds')
        
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
    exit(1)

# Run the bot
if __name__ == "__main__":
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        exit(1)