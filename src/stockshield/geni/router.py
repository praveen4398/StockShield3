"""FastAPI router exposing GENI conversational explanation endpoints."""

from typing import List

from fastapi import APIRouter, HTTPException, status

from stockshield.geni.context_builder import (
    AnalysisFailedError,
    AnalysisInconsistentError,
    AnalysisNotReadyError,
    RunNotFoundError,
)
from stockshield.geni.conversation_manager import (
    ConversationNotFoundError,
    ConversationRunMismatchError,
)
from stockshield.geni.models import (
    GeniChatRequest,
    GeniChatResponse,
    GeniConversationInfo,
    GeniMessage,
)
from stockshield.geni.service import GeniService

geni_router = APIRouter(prefix="/geni", tags=["GENI Assistant"])
_service = GeniService()


@geni_router.post(
    "/chat",
    response_model=GeniChatResponse,
    summary="Ask GENI a question about a completed stock analysis",
    description="Provides grounded, multi-turn natural language explanations for completed StockShield analysis runs.",
    responses={
        200: {"description": "Grounded explanation successfully generated."},
        400: {"description": "Analysis not ready/failed, or conversation_id belongs to a different run."},
        404: {"description": "Target run_id or conversation_id not found."},
        422: {"description": "Request validation or path traversal violation."},
        500: {"description": "Internal server error."},
    },
)
def chat_with_geni(request: GeniChatRequest) -> GeniChatResponse:
    """Submit a question to GENI regarding a completed stock analysis run."""
    try:
        response = _service.ask(request)
        return response
    except RunNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (ConversationRunMismatchError, AnalysisNotReadyError, AnalysisFailedError, AnalysisInconsistentError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GENI service encountered an unexpected error: {str(e)}",
        )


@geni_router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[GeniMessage],
    summary="Retrieve chat messages for a conversation thread",
)
def get_conversation_messages(conversation_id: str) -> List[GeniMessage]:
    """Fetch chronological message history for a conversation thread."""
    info = _service.conversation_manager.get_conversation(conversation_id)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return _service.conversation_manager.get_messages(conversation_id, limit=50)


@geni_router.get(
    "/conversations/run/{run_id}",
    response_model=List[GeniConversationInfo],
    summary="List all conversation threads associated with an analysis run",
)
def list_conversations_for_run(run_id: str) -> List[GeniConversationInfo]:
    """List conversation threads belonging to a specific run_id."""
    return _service.conversation_manager.list_conversations_for_run(run_id)
