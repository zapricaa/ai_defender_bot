import discord
from discord.ext import commands
import time
from typing import Dict, List
from collections import defaultdict
import asyncio

class AntiNukeModule:
    """
    Protection against server destruction attempts including:
    - Mass channel deletion
    - Mass role deletion
    - Permission escalations
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config.MODULE_SETTINGS['anti_nuke']
        self.channel_deletions: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.role_deletions: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.admin_changes: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        
    async def initialize(self):
        """Set up event listeners"""
        self.bot.add_listener(self.on_guild_channel_delete)
        self.bot.add_listener(self.on_guild_role_delete)
        self.bot.add_listener(self.on_member_update)
        
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Detect mass channel deletions"""
        guild = channel.guild
        user = guild.me.guild_permissions.view_audit_log and await self._get_last_deletor(guild)
        if not user:
            return
            
        self.channel_deletions[guild.id][user.id] += 1
        
        if self.channel_deletions[guild.id][user.id] > self.config['max_channel_deletes']:
            await self._handle_attack(guild, user, "Mass channel deletion")
            
    async def on_guild_role_delete(self, role: discord.Role):
        """Detect mass role deletions"""
        guild = role.guild
        user = guild.me.guild_permissions.view_audit_log and await self._get_last_deletor(guild)
        if not user:
            return
            
        self.role_deletions[guild.id][user.id] += 1
        
        if self.role_deletions[guild.id][user.id] > self.config['max_role_deletes']:
            await self._handle_attack(guild, user, "Mass role deletion")
            
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Detect role permission escalations"""
        if before.roles == after.roles:
            return
            
        guild = after.guild
        user = guild.me.guild_permissions.view_audit_log and await self._get_last_role_updater(guild)
        if not user:
            return
            
        added_roles = [r for r in after.roles if r not in before.roles]
        dangerous_roles = [r for r in added_roles if r.permissions.administrator]
        
        if dangerous_roles:
            self.admin_changes[guild.id][user.id] += 1
            
            if self.admin_changes[guild.id][user.id] > 1:
                await self._handle_attack(guild, user, "Admin permission escalation")
                
    async def _get_last_deletor(self, guild: discord.Guild) -> Optional[discord.Member]:
        """Get the last user who deleted a channel/role"""
        try:
            async for entry in guild.audit_logs(
                limit=1,
                action=discord.AuditLogAction.channel_delete
            ):
                return entry.user
        except discord.Forbidden:
            self.bot.logger.warning(f"No audit log access in {guild.id}")
            return None
            
    async def _get_last_role_updater(self, guild: discord.Guild) -> Optional[discord.Member]:
        """Get the last user who modified roles"""
        try:
            async for entry in guild.audit_logs(
                limit=1,
                action=discord.AuditLogAction.member_role_update
            ):
                return entry.user
        except discord.Forbidden:
            self.bot.logger.warning(f"No audit log access in {guild.id}")
            return None
            
    async def _handle_attack(self, guild: discord.Guild, user: discord.Member, reason: str):
        """Handle detected attack"""
        try:
            # Disable attacker's permissions first
            if guild.me.guild_permissions.administrator:
                for role in user.roles[1:]:  # Skip @everyone
                    try:
                        await role.edit(permissions=discord.Permissions.none(), reason="Anti-nuke protection")
                    except:
                        continue
                        
            # Ban the attacker
            try:
                await user.ban(reason=reason, delete_message_days=1)
            except discord.Forbidden:
                pass
                
            # Notify server
            await self._send_alert(guild, f"{user} was banned for {reason}")
            
            # Log action
            await self.bot.db.execute(
                "INSERT INTO moderation_logs (server_id, user_id, action, reason, moderator_id, timestamp) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (guild.id, user.id, "ban", reason, self.bot.user.id)
            )
            
            # Restore from backup if damage was done
            if len(guild.channels) < 3 or len(guild.roles) < 3:
                await self.bot.backup_manager.restore_guild(guild.id)
                
        except Exception as e:
            self.bot.logger.error(f"Error handling nuke attack: {str(e)}")
            
    async def _send_alert(self, guild: discord.Guild, message: str):
        """Send alert to server's default channel"""
        try:
            await guild.system_channel.send(
                f"🚨 **Security Alert**: {message}\n"
                "The incident has been logged."
            )
        except:
            # Try any text channel
            for channel in guild.text_channels:
                try:
                    await channel.send(message)
                    break
                except:
                    continue
