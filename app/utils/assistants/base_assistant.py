from abc import ABC, abstractmethod

from app.models.conversation_models import Conversation


class Assistant(ABC):

    @abstractmethod
    def invoke(self, conversation: Conversation, user_message: str) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_title(message: str) -> str:
        pass
