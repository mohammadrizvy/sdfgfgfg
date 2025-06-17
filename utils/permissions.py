from discord.ext import commands
from .config import ADMIN_ROLES, SUPPORT_ROLES

def is_admin():
    async def predicate(ctx):
        return any(role.name in ADMIN_ROLES for role in ctx.author.roles)
    return commands.check(predicate)

def is_support():
    async def predicate(ctx):
        return any(role.name in SUPPORT_ROLES for role in ctx.author.roles)
    return commands.check(predicate)

def check_ticket_permission(ctx):
    """Check if user can manage tickets"""
    return ctx.author.guild_permissions.administrator or any(
        role.name == "Ticket Manager" for role in ctx.author.roles
    )

