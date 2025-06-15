from discord.ext import commands

def is_admin(ctx):
    """Check if user has admin permissions"""
    return ctx.author.guild_permissions.administrator

def check_ticket_permission(ctx):
    """Check if user can manage tickets"""
    return ctx.author.guild_permissions.administrator or any(
        role.name == "Ticket Manager" for role in ctx.author.roles
    )

