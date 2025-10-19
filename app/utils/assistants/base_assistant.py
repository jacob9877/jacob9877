from abc import ABC, abstractmethod

from app.models.conversation_models import AssistantSlug


class Assistant(ABC):
    @property
    @abstractmethod
    def assistant_name(self) -> AssistantSlug:
        pass

    @abstractmethod
    def invoke(self, user_message: str) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_title(message: str) -> str:
        pass
