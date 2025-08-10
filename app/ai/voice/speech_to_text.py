import io
import logging
from typing import Optional
import speech_recognition as sr
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class SpeechToText:
    """Convert speech to text"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
    
    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio data to text"""
        try:
            # Convert bytes to audio
            audio_io = io.BytesIO(audio_data)
            audio_segment = AudioSegment.from_file(audio_io)
            
            # Convert to WAV format
            wav_io = io.BytesIO()
            audio_segment.export(wav_io, format="wav")
            wav_io.seek(0)
            
            # Recognize speech
            with sr.AudioFile(wav_io) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)
                
            logger.info(f"Transcribed: {text}")
            return text
            
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return "I couldn't understand what you said. Please try again."
        except sr.RequestError as e:
            logger.error(f"Speech recognition error: {str(e)}")
            return "I'm having trouble with speech recognition. Please try again later."
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return "There was an error processing your voice message."