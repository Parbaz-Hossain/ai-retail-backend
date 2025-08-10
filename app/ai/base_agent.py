from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all AI agents"""
    
    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.commands: Dict[str, callable] = {}
        self.initialized = False
    
    @abstractmethod
    async def initialize(self):
        """Initialize the agent"""
        pass
    
    @abstractmethod
    async def process_command(self, command: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a command"""
        pass
    
    async def cleanup(self):
        """Cleanup agent resources"""
        logger.info(f"🧹 Cleaning up {self.agent_type} agent")