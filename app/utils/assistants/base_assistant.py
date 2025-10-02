from abc import ABC, abstractmethod

from app.models.conversation_models import AssistantSlug, Conversation


class Assistant(ABC):

    @property
    @abstractmethod
    def assistant_name(self) -> AssistantSlug:
        pass

    @abstractmethod
    def invoke(self, conversation: Conversation, user_message: str) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_title(message: str) -> str:
        pass
