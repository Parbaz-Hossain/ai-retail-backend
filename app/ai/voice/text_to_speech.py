import io
import logging
from typing import Optional
from gtts import gTTS
import tempfile
import os

logger = logging.getLogger(__name__)

class TextToSpeech:
    """Convert text to speech"""
    
    def __init__(self):
        self.language = 'en'
        self.slow = False
    
    async def generate(self, text: str) -> Optional[bytes]:
        """Generate speech audio from text"""
        try:
            if not text or len(text.strip()) == 0:
                return None
            
            # Create TTS object
            tts = gTTS(text=text, lang=self.language, slow=self.slow)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                tts.save(tmp_file.name)
                
                # Read the file as bytes
                with open(tmp_file.name, 'rb') as audio_file:
                    audio_data = audio_file.read()
                
                # Clean up temporary file
                os.unlink(tmp_file.name)
                
            logger.info(f"Generated TTS for: {text[:50]}...")
            return audio_data
            
        except Exception as e:
            logger.error(f"Error generating TTS: {str(e)}")
            return None