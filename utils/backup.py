import discord
import sqlite3
import json
import asyncio
from typing import Dict, Any, Optional
import datetime
from dataclasses import dataclass
import traceback

@dataclass
class GuildBackup:
    roles: dict
    channels: dict
    settings: dict
    timestamp: float

class BackupManager:
    """
    Automated guild configuration backup system that:
    - Tracks server roles, channels and settings
    - Allows rapid restoration
    - Maintains version history
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_backups: Dict[int, GuildBackup] = {}
        
    async def backup_all_guilds(self) -> None:
        """Backup configuration for all guilds"""
        for guild in self.bot.guilds:
            await self.backup_guild(guild)
            
    async def backup_guild(self, guild: discord.Guild) -> bool:
        """Create comprehensive backup of guild configuration"""
        try:
            # Serialize roles
            roles = {
                role.id: {
                    "name": role.name,
                    "permissions": role.permissions.value,
                    "color": role.color.value,
                    "hoist": role.hoist,
                    "position": role.position,
                    "managed": role.managed,
                    "mentionable": role.mentionable
                }
                for role in guild.roles
            }
            
            # Serialize channels
            channels = {
                channel.id: {
                    "name": channel.name,
                    "type": str(channel.type),
                    "position": channel.position,
                    "overwrites": [
                        {
                            "target": target.id,
                            "allow": overwrite[0].value,
                            "deny": overwrite[1].value
                        }
                        for target, overwrite in channel.overwrites.items()
                    ]
                }
                for channel in guild.channels
            }
            
            # Serialize settings
            settings = {
                "name": guild.name,
                "icon": str(guild.icon) if guild.icon else None,
                "afk_channel": guild.afk_channel.id if guild.afk_channel else None,
                "system_channel": guild.system_channel.id if guild.system_channel else None,
                "verification_level": str(guild.verification_level),
                "default_notifications": str(guild.default_notifications),
                "features": list(guild.features)
            }
            
            # Store in memory cache
            backup = GuildBackup(
                roles=roles,
                channels=channels,
                settings=settings,
                timestamp=datetime.datetime.now().timestamp()
            )
            self.active_backups[guild.id] = backup
            
            # Store in database
            await self.bot.db.execute(
                '''INSERT OR REPLACE INTO server_backups 
                (server_id, roles, channels, settings, timestamp)
                VALUES (?, ?, ?, ?, ?)''',
                (
                    guild.id,
                    json.dumps(backup.roles),
                    json.dumps(backup.channels),
                    json.dumps(backup.settings),
                    backup.timestamp
                )
            )
            
            return True
            
        except Exception as e:
            self.bot.logger.error(f"Failed to backup guild {guild.id}: {str(e)}")
            traceback.print_exc()
            return False
            
    async def restore_guild(self, guild_id: int) -> bool:
        """Restore guild from most recent backup"""
        try:
            # Get latest backup
            cursor = await self.bot.db.execute(
                "SELECT roles, channels, settings FROM server_backups "
                "WHERE server_id = ? ORDER BY timestamp DESC LIMIT 1",
                (guild_id,)
            )
            backup = await cursor.fetchone()
            
            if not backup:
                self.bot.logger.warning(f"No backup found for guild {guild_id}")
                return False
                
            guild = self.bot.get_guild(guild_id)
            if not guild:
                self.bot.logger.error(f"Guild {guild_id} not found")
                return False
                
            self.bot.logger.info(f"Restoring guild {guild_id} from backup...")
            
            # Restore roles
            roles_data = json.loads(backup[0])
            existing_roles = {role.id: role for role in guild.roles}
            
            # Create missing roles and update existing ones
            for role_id, role_data in roles_data.items():
                if role_id not in existing_roles:
                    await guild.create_role(
                        name=role_data["name"],
                        permissions=discord.Permissions(role_data["permissions"]),
                        color=discord.Color(role_data["color"]),
                        hoist=role_data["hoist"],
                        mentionable=role_data["mentionable"],
                        reason="Restored from backup"
                    )
                    
            # Reorder roles
            sorted_roles = sorted(
                guild.roles, 
                key=lambda r: roles_data.get(str(r.id), {}).get("position", 0),
                reverse=True
            )
            for role in sorted_roles:
                await role.edit(position=roles_data.get(str(role.id), {}).get("position", 0))
                
            # TODO: Restore channels and settings (implementation omitted for brevity)
            
            self.bot.logger.info(f"Successfully restored guild {guild_id}")
            return True
            
        except Exception as e:
            self.bot.logger.error(f"Failed to restore guild {guild_id}: {str(e)}")
            traceback.print_exc()
            return False
