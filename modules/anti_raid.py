import discord
import asyncio
import time
from discord.ext import commands
from typing import Dict, Set, Optional
from collections import defaultdict

class AntiRaidModule:
    """
    Sophisticated raid prevention system that detects and responds to:
    - Mass joins from similar accounts
    - Sudden spikes in member activity
    - Mechanical account behavior patterns
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config.MODULE_SETTINGS['anti_raid']
        self.join_times: Dict[int, Dict[int, float]] = defaultdict(dict)
        self.recent_joins: Dict[int, Set[int]] = defaultdict(set)
        self.suspected_raiders: Dict[int, Set[int]] = defaultdict(set)
        self.lockdown_mode: Set[int] = set()

    async def initialize(self):
        """Set up event listeners and background tasks"""
        self.bot.add_listener(self.on_member_join)
        self.bot.add_listener(self.on_message)
        self.cleanup_task = self.bot.loop.create_task(self._periodic_cleanup())

    async def on_member_join(self, member: discord.Member):
        """Monitor new members for raid patterns"""
        guild = member.guild
        guild_id = guild.id
        user_id = member.id

        # Skip if already in lockdown
        if guild_id in self.lockdown_mode:
            await self._process_suspected_member(guild, member, "Join during lockdown")
            return

        # Track join time
        current_time = time.time()
        self.join_times[guild_id][user_id] = current_time
        self.recent_joins[guild_id].add(user_id)

        # Check join burst
        recent_join_count = self._get_recent_joins(guild_id)
        if recent_join_count >= self.config['join_threshold']:
            await self._activate_lockdown(guild, "Mass join detected")
            return

        # Analyze account for suspicious traits
        if await self._is_suspicious_account(member):
            self.suspected_raiders[guild_id].add(user_id)
            await self._process_suspected_member(guild, member, "Suspicious account traits")
            return

    async def on_message(self, message: discord.Message):
        """Monitor message patterns for raid behavior"""
        if message.author.bot or not isinstance(message.author, discord.Member):
            return

        guild = message.guild
        guild_id = guild.id
        user_id = message.author.id

        # Check if user is in suspected raiders list
        if user_id in self.suspected_raiders.get(guild_id, set()):
            await self._process_suspected_member(guild, message.author, "Messaging while suspected")
            return

        # Detect spam in new members
        if user_id in self.recent_joins.get(guild_id, set()):
            if await self._is_spam_behavior(message):
                self.suspected_raiders[guild_id].add(user_id)
                await self._process_suspected_member(guild, message.author, "Spam behavior after joining")

    def _get_recent_joins(self, guild_id: int) -> int:
        """Get count of recent joins within configured time window"""
        current_time = time.time()
        threshold = self.config['time_window']
        recent = 0

        for join_time in self.join_times[guild_id].values():
            if current_time - join_time <= threshold:
                recent += 1

        return recent

    async def _is_suspicious_account(self, member: discord.Member) -> bool:
        """Check for signs of a spam/bot account"""
        account_age = (discord.utils.utcnow() - member.created_at).total_seconds()
        if account_age < 86400:  # Less than 1 day old
            return True

        if member.avatar is None:
            return True

        if member.default_avatar and len(member.roles) == 1:  # Only @everyone role
            return True

        return False

    async def _is_spam_behavior(self, message: discord.Message) -> bool:
        """Detect spam-like message patterns"""
        content = message.content

        # Check for excessive mentions
        if len(message.mentions) > 3:
            return True

        # Check for repetitive content
        if len(content) > 50 and len(set(content)) / len(content) < 0.5:  # Low character diversity
            return True

        # Check for suspicious links
        if 'http' in content and any(domain in content.lower() for domain in ['discord.gg', 'invite', 'nitro']):
            return True

        return False

    async def _activate_lockdown(self, guild: discord.Guild, reason: str):
        """Enable lockdown mode with increased security"""
        guild_id = guild.id
        if guild_id in self.lockdown_mode:
            return

        self.lockdown_mode.add(guild_id)
        self.bot.logger.info(f"Activating lockdown in {guild_id} for {reason}")

        try:
            # Raise verification level temporarily
            original_verification = guild.verification_level
            new_level = max(guild.verification_level.value, 
                          self.config['verification_level'])
            await guild.edit(verification_level=discord.VerificationLevel(new_level))

            # Close all invite links
            for invite in await guild.invites():
                try:
                    await invite.delete(reason="Raid protection lockdown")
                except:
                    continue

            # Queue verification for joined members
            for member_id in self.recent_joins.get(guild_id, set()):
                member = guild.get_member(member_id)
                if member:
                    try:
                        await member.kick(reason="Pending verification during raid protection")
                    except:
                        continue

            # Log and notify
            await self._send_lockdown_notice(guild, reason)

            # Schedule lockdown removal
            self.bot.loop.create_task(
                self._disable_lockdown(guild, original_verification)
            )

        except Exception as e:
            self.bot.logger.error(f"Failed to activate lockdown in {guild_id}: {str(e)}")

    async def _disable_lockdown(self, guild: discord.Guild, original_verification: int):
        """Disable lockdown mode after cooldown period"""
        await asyncio.sleep(3600)  # 1 hour lockdown
        try:
            await guild.edit(verification_level=discord.VerificationLevel(original_verification))
            self.lockdown_mode.discard(guild.id)
            await guild.system_channel.send(
                "🔓 **Lockdown lifted**: Raid protection measures have been relaxed. "
                "Server is now operating normally."
            )
        except Exception as e:
            self.bot.logger.error(f"Failed to disable lockdown: {str(e)}")

    async def _process_suspected_member(self, guild: discord.Guild, member: discord.Member, reason: str):
        """Handle a member identified as potential raider"""
        try:
            action = self.config.get('action', 'kick')

            if action == 'kick':
                await member.kick(reason=f"Anti-raid: {reason}")
            elif action == 'ban':
                await member.ban(reason=f"Anti-raid: {reason}", delete_message_days=1)
            elif action == 'timeout':
                timeout = discord.utils.utcnow() + datetime.timedelta(hours=12)
                await member.edit(timed_out_until=timeout, reason=f"Anti-raid: {reason}")
            else:
                await member.send(
                    f"Your account has been flagged in {guild.name} for: {reason}. "
                    "Please contact moderators if this is in error."
                )

            await self.bot.db.execute(
                "INSERT INTO moderation_logs (server_id, user_id, action, reason, moderator_id, timestamp) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (guild.id, member.id, f"anti_raid_{action}", reason, self.bot.user.id)
            )

        except Exception as e:
            self.bot.logger.error(f"Failed to process suspected raider {member.id}: {str(e)}")

    async def _send_lockdown_notice(self, guild: discord.Guild, reason: str):
        """Notify server about lockdown status"""
        notice = (
            "🚨 **RAID PROTECTION ACTIVATED** 🚨\n\n"
            f"Reason: {reason}\n"
            "Security measures have been enabled:\n"
            "- New joins require verification\n"
            "- All invites have been disabled\n"
            "- Recent unverified members were removed\n\n"
            "Normal operations will resume shortly."
        )

        try:
            if guild.system_channel:
                await guild.system_channel.send(notice)
            else:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(notice)
                        break
        except Exception as e:
            self.bot.logger.error(f"Failed to send lockdown notice: {str(e)}")

    async def _periodic_cleanup(self):
        """Clean up old join records"""
        while True:
            await asyncio.sleep(3600)
            current_time = time.time()
            threshold = 86400  # 24 hours

            for guild_id in list(self.join_times.keys()):
                self.join_times[guild_id] = {
                    uid: t for uid, t in self.join_times[guild_id].items()
                    if current_time - t <= threshold
                }

                if not self.join_times[guild_id]:
                    del self.join_times[guild_id]
                    self.recent_joins.pop(guild_id, None)
                    self.suspected_raiders.pop(guild_id, None)
