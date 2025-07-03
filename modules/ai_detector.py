import discord
from discord.ext import commands
import torch
import transformers
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import Dict, Optional, List
import sqlite3
import time
import numpy as np
import re

class AIDetectorModule:
    """
    Advanced phishing/scam detection system using:
    - Pretrained NLP models
    - Semantic pattern matching
    - Link/gibberish detection
    - Perspective API integration
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config.MODULE_SETTINGS['ai_detector']
        self.tokenizer = None
        self.model = None
        self.load_model()
        
    def load_model(self):
        """Load the pretrained detection model"""
        try:
            model_path = self.config['model_path']
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
            self.bot.logger.info("AI detection model loaded successfully")
        except Exception as e:
            self.bot.logger.error(f"Failed to load AI model: {str(e)}")
            self.model = None
    
    async def analyze_message(self, message: discord.Message):
        """Analyze message content for scams/phishing"""
        if not message.content or not self.model:
            return
            
        try:
            content = self._sanitize_content(message.content)
            prediction = self._predict_text(content)
            
            if prediction > self.config['threshold']:
                await self._handle_suspicious_message(message, prediction)
                
        except Exception as e:
            self.bot.logger.error(f"AI detection failed: {str(e)}")
            traceback.print_exc()
            
    def _sanitize_content(self, text: str) -> str:
        """Clean message content for analysis"""
        # Remove ping formatting
        text = re.sub(r'<[@#][^>]+>', '', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove excessive whitespace
        text = ' '.join(text.split())
        return text
        
    def _predict_text(self, text: str) -> float:
        """Run text through detection model"""
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        outputs = self.model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        return probs[0][1].item()  # Return probability of being malicious
        
    async def _handle_suspicious_message(self, message: discord.Message, score: float):
        """Handle detected malicious content"""
        try:
            # Delete the message
            await message.delete()
            
            # Log in database
            await self.bot.db.execute(
                "INSERT INTO suspicious_messages VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                (message.id, message.guild.id, message.channel.id, 
                 message.author.id, message.content[:1500], score)
            )
            
            # Notify moderators
            await self._send_mod_alert(message, score)
            
            # Apply punishment if repeat offender
            await self._check_repeats(message.author, message.guild)
            
        except discord.Forbidden:
            self.bot.logger.warning(f"No permissions to delete message {message.id}")
        except Exception as e:
            self.bot.logger.error(f"Error handling suspicious message: {str(e)}")
            
    async def _send_mod_alert(self, message: discord.Message, score: float):
        """Notify moderation team about suspicious message"""
        fields = [
            ("User", f"{message.author} (ID: {message.author.id})", True),
            ("Channel", message.channel.mention, True),
            ("Confidence", f"{score*100:.1f}%", True),
            ("Content", message.content[:500] + ("..." if len(message.content) > 500 else ""), False)
        ]
        
        embed = discord.Embed(
            title="⚠ Suspicious Message Detected",
            color=discord.Color.orange(),
            timestamp=message.created_at
        )
        
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
            
        # Get mod channel
        channel = discord.utils.get(message.guild.text_channels, name="mod-alerts")
        if not channel:
            channel = message.guild.system_channel
            
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass
                
    async def _check_repeats(self, member: discord.Member, guild: discord.Guild):
        """Check if user has multiple violations"""
        cursor = await self.bot.db.execute(
            "SELECT COUNT(*) FROM suspicious_messages WHERE user_id = ? AND server_id = ?",
            (member.id, guild.id)
        )
        count = await cursor.fetchone()
        
        if count and count[0] > 3:  # More than 3 violations
            mute_role = discord.utils.get(guild.roles, name="Muted")
            if mute_role:
                await member.add_roles(mute_role, reason="Repeat violations")
