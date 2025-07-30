from abc import ABC, abstractmethod

class BaseFeature(ABC):
    @abstractmethod
    def run(self, file_path: str):
        pass