import os
import json
from dotenv import load_dotenv
from typing import Dict, Any, Optional

class Config:
    """Centralized configuration management for AI Defender Bot"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from environment and config file"""
        load_dotenv()
        
        # Core settings
        self.TOKEN: str = os.getenv('DISCORD_TOKEN')
        self.COMMAND_PREFIX: str = os.getenv('COMMAND_PREFIX', '!')
        self.OWNER_IDS: list[int] = [int(x) for x in os.getenv('OWNER_IDS', '').split(',') if x]
        
        # Database settings
        self.BACKUP_INTERVAL: int = int(os.getenv('BACKUP_INTERVAL', 3600))  # Default 1 hour
        self.MAX_MESSAGE_HISTORY: int = int(os.getenv('MAX_MESSAGE_HISTORY', 1000))
        
        # Module configurations
        self.MODULE_SETTINGS: Dict[str, Dict[str, Any]] = {
            'anti_spam': {
                'message_threshold': int(os.getenv('ANTI_SPAM_THRESHOLD', 5)),
                'time_window': int(os.getenv('ANTI_SPAM_WINDOW', 10)),
                'punishment': os.getenv('ANTI_SPAM_PUNISHMENT', 'mute'),
                'duration': int(os.getenv('ANTI_SPAM_DURATION', 300))
            },
            'anti_nuke': {
                'max_channel_deletes': int(os.getenv('MAX_CHANNEL_DELETES', 3)),
                'max_role_deletes': int(os.getenv('MAX_ROLE_DELETES', 3)),
                'ban_threshold': int(os.getenv('BAN_THRESHOLD', 5))
            },
            'anti_raid': {
                'join_threshold': int(os.getenv('JOIN_THRESHOLD', 10)),
                'time_window': int(os.getenv('JOIN_WINDOW', 60)),
                'verification_level': int(os.getenv('VERIFICATION_LEVEL', 1))
            },
            'ai_detector': {
                'model_path': os.getenv('AI_MODEL_PATH', 'models/scam_detector.h5'),
                'threshold': float(os.getenv('AI_THRESHOLD', 0.85)),
                'api_key': os.getenv('PERSPECTIVE_API_KEY')
            }
        }
        
        # Load additional settings from config file if present
        self._load_config_file()
        
    def _load_config_file(self) -> None:
        """Load additional settings from config.json"""
        try:
            with open('config.json', 'r') as f:
                file_config = json.load(f)
            
            if 'module_settings' in file_config:
                for module, settings in file_config['module_settings'].items():
                    if module in self.MODULE_SETTINGS:
                        self.MODULE_SETTINGS[module].update(settings)
            
        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid config.json: {str(e)}")
    
    def get_setting(self, module: str, setting: str, default: Optional[Any] = None) -> Any:
        """Get a specific module setting"""
        return self.MODULE_SETTINGS.get(module, {}).get(setting, default)

# Example config.json structure:
"""
{
    "module_settings": {
        "anti_spam": {
            "message_threshold": 7,
            "time_window": 15
        },
        "ai_detector": {
            "threshold": 0.9
        }
    }
}
"""

