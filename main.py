import discord
from discord.ext import commands
from config import Config
from modules import anti_spam, anti_nuke, anti_raid, watchdog, ai_detector
from utils.logger import setup_logger
from utils.backup import BackupManager
import asyncio
import sqlite3
import traceback

class AIDefenderBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = Config()
        self.logger = setup_logger('ai_defender')
        self.backup_manager = BackupManager(self)
        self.db_connection = sqlite3.connect('database.db')
        self._setup_db()
        
        # Initialize modules
        self.anti_spam = anti_spam.AntiSpamModule(self)
        self.anti_nuke = anti_nuke.AntiNukeModule(self)
        self.anti_raid = anti_raid.AntiRaidModule(self)
        self.watchdog = watchdog.WatchdogModule(self)
        self.ai_detector = ai_detector.AIDetectorModule(self)

    def _setup_db(self):
        """Initialize database tables if they don't exist"""
        cursor = self.db_connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_backups (
                server_id INTEGER PRIMARY KEY,
                roles BLOB,
                channels BLOB,
                settings BLOB,
                timestamp DATETIME
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moderation_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER,
                user_id INTEGER,
                action TEXT,
                reason TEXT,
                moderator_id INTEGER,
                timestamp DATETIME
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suspicious_messages (
                message_id INTEGER PRIMARY KEY,
                server_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                content TEXT,
                score REAL,
                timestamp DATETIME
            )
        ''')
        self.db_connection.commit()

    async def on_ready(self):
        """Called when the bot is ready"""
        self.logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        self.logger.info(f'Connected to {len(self.guilds)} guilds')
        
        # Initialize modules
        await self.anti_spam.initialize()
        await self.anti_nuke.initialize()
        await self.anti_raid.initialize()
        await self.watchdog.initialize()
        await self.ai_detector.initialize()
        
        # Schedule periodic backups
        self.loop.create_task(self._periodic_backups())

    async def _periodic_backups(self):
        """Perform periodic backups of server configurations"""
        while True:
            try:
                await self.backup_manager.backup_all_guilds()
                await asyncio.sleep(self.config.BACKUP_INTERVAL)
            except Exception as e:
                self.logger.error(f'Periodic backup failed: {str(e)}')
                await asyncio.sleep(60)  # Wait before retrying

    async def on_message(self, message):
        """Process all incoming messages"""
        if message.author.bot:
            return
            
        try:
            # Anti-spam checks
            if await self.anti_spam.process_message(message):
                return
                
            # AI detection
            await self.ai_detector.analyze_message(message)
            
        except Exception as e:
            self.logger.error(f'Error processing message: {str(e)}')
            traceback.print_exc()
            
        finally:
            await self.process_commands(message)

    async def close(self):
        """Clean up before shutting down"""
        self.logger.info('Shutting down...')
        await self.backup_manager.backup_all_guilds()
        self.db_connection.close()
        await super().close()

if __name__ == '__main__':
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.members = True
    intents.message_content = True
    
    bot = AIDefenderBot(
        command_prefix=Config().COMMAND_PREFIX,
        intents=intents,
        case_insensitive=True,
        allowed_mentions=discord.AllowedMentions(everyone=False, roles=False)
    )
    
    try:
        bot.run(Config().TOKEN)
    except Exception as e:
        bot.logger.critical(f'Fatal error: {str(e)}')

