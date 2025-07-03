import asyncio
import discord
import time
import psutil
import socket
from discord.ext import commands
from typing import Optional, Dict
from datetime import datetime

class WatchdogModule:
    """
    System health monitoring and recovery watchdog that tracks:
    - Bot performance metrics
    - Resource usage
    - Network connectivity
    - Module health checks
    - Automated recovery procedures
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()
        self.performance_stats = {
            'event_lag': [],      # Track event processing delays
            'command_latency': [],  # Track command response times
            'api_errors': 0,      # Track API error rate
            'reconnects': 0       # Track websocket reconnects
        }
        self.module_health = {}
        self.resource_stats = {
            'cpu_usage': [],
            'memory_usage': [],
            'network_usage': []
        }
        self.last_incident = None

    async def initialize(self):
        """Start monitoring tasks"""
        self.monitor_task = self.bot.loop.create_task(self._monitor_system())
        self.health_check_task = self.bot.loop.create_task(self._periodic_health_checks())
        
        # Register error handlers
        self.bot.add_listener(self.on_error)
        self.bot.add_listener(self.on_socket_event_type)

    async def _monitor_system(self):
        """Continuous system monitoring loop"""
        while True:
            try:
                # Track CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self._update_rolling_stats('cpu_usage', cpu_percent, 60)
                
                # Track memory usage
                mem_info = psutil.Process().memory_info()
                mem_percent = (mem_info.rss / psutil.virtual_memory().total) * 100
                self._update_rolling_stats('memory_usage', mem_percent, 60)
                
                # Check thresholds and alert
                if cpu_percent > 90:
                    await self._handle_resource_alert("High CPU", f"{cpu_percent:.1f}% usage")
                    
                if mem_percent > 90:
                    await self._handle_resource_alert("High memory", f"{mem_percent:.1f}% usage")
                    
                # Network connectivity check
                if not await self._check_network():
                    await self._handle_network_outage()
                
                await asyncio.sleep(30)
                
            except Exception as e:
                self.bot.logger.error(f"Monitoring error: {str(e)}")
                await asyncio.sleep(60)

    def _update_rolling_stats(self, metric: str, value: float, max_samples: int):
        """Maintain rolling window of metrics"""
        if metric not in self.resource_stats:
            self.resource_stats[metric] = []
            
        self.resource_stats[metric].append(value)
        if len(self.resource_stats[metric]) > max_samples:
            self.resource_stats[metric].pop(0)

    async def _check_network(self) -> bool:
        """Check essential network connectivity"""
        try:
            # Check Discord API
            async with self.bot.session.get('https://discord.com/api/v9/gateway'):
                pass
                
            # Check database connectivity
            with self.bot.db.execute("SELECT 1"):
                pass
                
            return True
        except:
            return False

    async def _handle_resource_alert(self, alert_type: str, details: str):
        """Handle resource threshold alerts"""
        if self.last_incident and time.time() - self.last_incident < 300:
            return  # Cooldown
            
        self.last_incident = time.time()
        owner_notice = (
            f"⚠️ **System Alert**: {alert_type}\n"
            f"Details: {details}\n"
            f"Uptime: {self._format_uptime()}\n"
            f"Bot version: {self.bot.version}"
        )
        
        for owner_id in self.bot.config.OWNER_IDS:
            owner = self.bot.get_user(owner_id)
            if owner:
                try:
                    await owner.send(owner_notice)
                except:
                    continue

    async def _handle_network_outage(self):
        """Handle network connectivity issues"""
        retries = 0
        while retries < 3:
            if await self._check_network():
                return
                
            await asyncio.sleep(10)
            retries += 1
            
        # If still failing after retries
        self.bot.logger.critical("Persistent network outage detected")
        if not self.bot.is_closed():
            await self.bot.close()
            
    async def on_error(self, event_method: str, *args, **kwargs):
        """Track errors from event handlers"""
        self.performance_stats['api_errors'] += 1
        self.bot.logger.error(f"Error in {event_method}: {str(args[0]) if args else 'Unknown'}")

    async def on_socket_event_type(self, event_type: str):
        """Track websocket events"""
        if event_type == 'RESUMED':
            self.performance_stats['reconnects'] += 1
            self.bot.logger.warning("Websocket reconnected")

    async def _periodic_health_checks(self):
        """Run automated health checks on all modules"""
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            
            # Check module responsiveness
            modules = {
                'anti_spam': self.bot.anti_spam,
                'anti_nuke': self.bot.anti_nuke,
                'anti_raid': self.bot.anti_raid,
                'ai_detector': self.bot.ai_detector
            }
            
            for name, module in modules.items():
                try:
                    # Simple ping test for each module
                    if hasattr(module, '_health_check'):
                        healthy = await module._health_check()
                    else:
                        healthy = True
                        
                    self.module_health[name] = {
                        'healthy': healthy,
                        'last_check': datetime.utcnow().isoformat()
                    }
                    
                    if not healthy:
                        self.bot.logger.warning(f"Module {name} health check failed")
                        
                except Exception as e:
                    self.module_health[name] = {
                        'healthy': False,
                        'error': str(e),
                        'last_check': datetime.utcnow().isoformat()
                    }
                    self.bot.logger.error(f"Health check failed for {name}: {str(e)}")

    def _format_uptime(self) -> str:
        """Format bot uptime as human-readable string"""
        uptime = int(time.time() - self.start_time)
        days, remainder = divmod(uptime, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return f"{days}d {hours}h {minutes}m {seconds}s"

    async def get_status_report(self) -> dict:
        """Generate comprehensive status report"""
        return {
            'uptime': self._format_uptime(),
            'performance': {
                'avg_cpu': self._get_avg('cpu_usage'),
                'avg_memory': self._get_avg('memory_usage'),
                'event_lag': self._get_avg('event_lag'),
                'api_errors': self.performance_stats['api_errors'],
                'reconnects': self.performance_stats['reconnects']
            },
            'module_health': self.module_health,
            'resource_usage': {
                'cpu': f"{self._get_avg('cpu_usage', 1):.1f}%",
                'memory': f"{self._get_avg('memory_usage', 1):.1f}%",
            },
            'last_incident': self.last_incident
        }

    def _get_avg(self, metric: str, decimals: int = 2) -> float:
        """Calculate average of a metric"""
        if not self.resource_stats.get(metric):
            return 0.0
        return round(sum(self.resource_stats[metric]) / len(self.resource_stats[metric]), decimals)
