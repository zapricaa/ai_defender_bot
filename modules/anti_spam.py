import discord
import asyncio
import time
from typing import Dict, List
from discord.ext import commands
from collections import defaultdict

class AntiSpamModule:
    """
    Advanced spam detection and prevention system that tracks:
    - Message frequency per user
    - Repeated content patterns
    - Mention spam
    - Unusual message patterns
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config.MODULE_SETTINGS['anti_spam']
        self.message_history: Dict[int, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
        self.repeat_offenders: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.user_last_warn: Dict[int, Dict[int, float]] = defaultdict(dict)
        
    async def initialize(self):
        """Initialize background tasks"""
        self.cleanup_task = self.bot.loop.create_task(self._periodic_cleanup())
        
    async def process_message(self, message: discord.Message) -> bool:
        """Process a message and determine if it's spam"""
        guild_id = message.guild.id
        user_id = message.author.id
        
        # Track message timing
        current_time = time.time()
        self.message_history[guild_id][user_id].append(current_time)
        
        # Check message frequency
        if self._check_message_frequency(guild_id, user_id):
            await self._take_action(message, "Excessive message frequency")
            return True
            
        # Check duplicate content
        if self._check_duplicate_content(message):
            await self._take_action(message, "Repeated message content")
            return True
            
        # Check mention spam
        if self._check_mention_spam(message):
            await self._take_action(message, "Mention spam")
            return True
            
        return False
        
    def _check_message_frequency(self, guild_id: int, user_id: int) -> bool:
        """Check if user exceeds message frequency threshold"""
        messages = self.message_history[guild_id][user_id]
        time_window = self.config['time_window']
        threshold = self.config['message_threshold']
        
        # Remove messages outside time window
        current_time = time.time()
        messages = [m for m in messages if current_time - m <= time_window]
        self.message_history[guild_id][user_id] = messages
        
        return len(messages) >= threshold
        
    def _check_duplicate_content(self, message: discord.Message) -> bool:
        """Check for repeated message content"""
        # TODO: Implement content similarity check
        return False
        
    def _check_mention_spam(self, message: discord.Message) -> bool:
        """Check for mention spam"""
        mention_threshold = self.config.get('mention_threshold', 5)
        return len(message.mentions) >= mention_threshold
        
    async def _take_action(self, message: discord.Message, reason: str):
        """Take appropriate action against spam"""
        action = self.config['punishment']
        duration = self.config['duration']
        
        guild = message.guild
        user = message.author
        guild_id = guild.id
        user_id = user.id
        
        # Warn user first (with cooldown)
        last_warn = self.user_last_warn[guild_id].get(user_id, 0)
        if time.time() - last_warn > 300:  # 5 min cooldown
            await message.channel.send(
                f"{user.mention}, your message was flagged as potential spam ({reason}). "
                "Please refrain from this behavior."
            )
            self.user_last_warn[guild_id][user_id] = time.time()
            return
            
        # Implement punishment
        try:
            if action == 'mute':
                mute_role = discord.utils.get(guild.roles, name="Muted")
                if mute_role:
                    await user.add_roles(mute_role, reason=reason)
                    if duration > 0:
                        await asyncio.sleep(duration)
                        await user.remove_roles(mute_role)
                    
            elif action == 'kick':
                await user.kick(reason=reason)
                
            elif action == 'ban':
                await user.ban(reason=reason, delete_message_days=1)
                
            self.repeat_offenders[guild_id][user_id] += 1
            await self.bot.db.execute(
                "INSERT INTO moderation_logs (server_id, user_id, action, reason, moderator_id, timestamp) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (guild_id, user_id, f"{action}_spam", reason, self.bot.user.id)
            )
            
        except discord.Forbidden:
            self.bot.logger.error(f"Missing permissions to punish {user_id} in {guild_id}")
            
    async def _periodic_cleanup(self):
        """Clean up old message history periodically"""
        while True:
            await asyncio.sleep(3600)  # Run hourly
            current_time = time.time()
            threshold = self.config['time_window']
            
            for guild_id in list(self.message_history.keys()):
                for user_id in list(self.message_history[guild_id].keys()):
                    self.message_history[guild_id][user_id] = [
                        t for t in self.message_history[guild_id][user_id] 
                        if current_time - t <= threshold * 2
                    ]
                    
                    if not self.message_history[guild_id][user_id]:
                        del self.message_history[guild_id][user_id]
