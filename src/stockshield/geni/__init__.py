"""GENI — StockShield AI Analysis Assistant.

Provides grounded conversational explanations for completed StockShield 2.0 multi-agent analyses.
"""

from stockshield.geni.client import GeniClient
from stockshield.geni.context_builder import GeniContextBuilder
from stockshield.geni.conversation_manager import GeniConversationManager
from stockshield.geni.models import GeniChatRequest, GeniChatResponse, GeniMessage
from stockshield.geni.router import geni_router
from stockshield.geni.service import GeniService

__all__ = [
    "GeniChatRequest",
    "GeniChatResponse",
    "GeniMessage",
    "GeniClient",
    "GeniContextBuilder",
    "GeniConversationManager",
    "GeniService",
    "geni_router",
]
