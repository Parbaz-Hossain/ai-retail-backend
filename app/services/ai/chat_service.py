import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.ai.agent_manager import AIAgentManager
from app.ai.nlp.text_processor import TextProcessor
from app.ai.voice.speech_to_text import SpeechToText
from app.ai.voice.text_to_speech import TextToSpeech
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.speech_to_text = SpeechToText()
        self.text_to_speech = TextToSpeech()
        
    async def process_text_message(
        self, 
        message: str, 
        user_id: int, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process text message through AI system"""
        try:
            # Process and understand the message
            processed = await self.text_processor.process(message)
            
            # Get AI agent manager from app state
            ai_manager = await self._get_ai_manager()
            
            # Add user context
            full_context = {
                **context,
                "user_id": user_id,
                "intent": processed.get("intent"),
                "entities": processed.get("entities", []),
                "timestamp": datetime.utcnow()
            }
            
            # Process through appropriate agent
            result = await ai_manager.process_command(message, full_context)
            
            # Generate audio response if needed
            audio_response = None
            if context.get("voice_enabled"):
                audio_response = await self.text_to_speech.generate(result["response"])
            
            # Store conversation
            await self._store_conversation(user_id, message, result["response"])
            
            return {
                "response": result["response"],
                "agent": result.get("agent", "unknown"),
                "timestamp": datetime.utcnow(),
                "context": full_context,
                "actions_taken": result.get("actions", []),
                "audio_response": audio_response
            }
            
        except Exception as e:
            logger.error(f"Error processing text message: {str(e)}")
            return {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "agent": "system",
                "timestamp": datetime.utcnow(),
                "error": str(e)
            }
    
    async def process_voice_message(
        self, 
        audio_data: bytes, 
        user_id: int, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process voice message through AI system"""
        try:
            # Convert speech to text
            text_message = await self.speech_to_text.transcribe(audio_data)
            
            # Process as text message with voice context
            voice_context = {**context, "voice_enabled": True}
            return await self.process_text_message(text_message, user_id, voice_context)
            
        except Exception as e:
            logger.error(f"Error processing voice message: {str(e)}")
            return {
                "response": "I had trouble understanding your voice message. Please try again.",
                "agent": "system",
                "timestamp": datetime.utcnow(),
                "error": str(e)
            }
    
    async def execute_command(self, command: str, user_id: int) -> Dict[str, Any]:
        """Execute AI command directly"""
        try:
            ai_manager = await self._get_ai_manager()
            context = {"user_id": user_id, "direct_command": True}
            
            result = await ai_manager.process_command(command, context)
            await self._store_conversation(user_id, command, result["response"])
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            return {"error": str(e), "status": "failed"}
    
    async def get_conversation_history(self, user_id: int) -> List[Dict[str, Any]]:
        """Get conversation history for user"""
        try:
            # Get from Redis cache
            history_key = f"conversation:{user_id}"
            history = await redis_client.lrange(history_key, 0, 50)  # Last 50 messages
            
            return [eval(msg) for msg in history] if history else []
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []
    
    async def _store_conversation(
        self, 
        user_id: int, 
        message: str, 
        response: str
    ):
        """Store conversation in Redis"""
        try:
            conversation_entry = {
                "user_message": message,
                "ai_response": response,
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id
            }
            
            history_key = f"conversation:{user_id}"
            await redis_client.lpush(history_key, str(conversation_entry))
            await redis_client.ltrim(history_key, 0, 99)  # Keep last 100 messages
            await redis_client.expire(history_key, 86400 * 30)  # 30 days
            
        except Exception as e:
            logger.error(f"Error storing conversation: {str(e)}")
    
    async def _get_ai_manager(self) -> AIAgentManager:
        """Get AI manager from app state"""
        # This would be injected in real implementation
        # For now, create a new instance
        return AIAgentManager()