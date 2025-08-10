# from fastapi import APIRouter, Depends, HTTPException, Request
# from typing import Dict, Any, List
# from app.schemas.system.ai_chat import ChatRequest, ChatResponse, VoiceRequest
# from app.services.ai.chat_service import ChatService
# from app.api.dependencies import get_current_user

# router = APIRouter()
# chat_service = ChatService()

# @router.post("/chat", response_model=ChatResponse)
# async def chat_with_ai(
#     request: ChatRequest,
#     current_user = Depends(get_current_user)
# ):
#     """Chat with AI agent using text input"""
#     try:
#         response = await chat_service.process_text_message(
#             message=request.message,
#             user_id=current_user.id,
#             context=request.context or {}
#         )
#         return ChatResponse(**response)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/voice", response_model=ChatResponse)
# async def voice_chat_with_ai(
#     request: VoiceRequest,
#     current_user = Depends(get_current_user)
# ):
#     """Chat with AI agent using voice input"""
#     try:
#         response = await chat_service.process_voice_message(
#             audio_data=request.audio_data,
#             user_id=current_user.id,
#             context=request.context or {}
#         )
#         return ChatResponse(**response)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/conversation/{user_id}", response_model=List[Dict])
# async def get_conversation_history(
#     user_id: int,
#     current_user = Depends(get_current_user)
# ):
#     """Get conversation history for a user"""
#     try:
#         history = await chat_service.get_conversation_history(user_id)
#         return history
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/command")
# async def execute_ai_command(
#     command: str,
#     current_user = Depends(get_current_user)
# ):
#     """Execute AI command directly"""
#     try:
#         result = await chat_service.execute_command(
#             command=command,
#             user_id=current_user.id
#         )
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))