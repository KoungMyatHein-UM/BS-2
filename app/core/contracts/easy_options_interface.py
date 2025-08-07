from abc import ABC, abstractmethod

class BaseEasyOptions(ABC):
    @abstractmethod
    def __init__(self, message: str):
        pass

    @abstractmethod
    def add_option(self, option_id: str, option_label: str, option_callable: callable) -> None:
        pass

    @abstractmethod
    def set_feature_name(self, feature_name: str) -> None:
        pass

    @abstractmethod
    def render(self) -> str:
        pass

    @abstractmethod
    def get_option_callable(self, option_id: str) -> callable:
        pass