from abc import ABC, abstractmethod

class BaseFeature(ABC):
    # ***** REQUIRED *****
    @abstractmethod
    def run(self, params: dict) -> str:
        pass

    # ***** OPTIONAL *****
    def self_test(self) -> bool:
        pass

    # ***** OPTIONAL *****
    def shutdown(self) -> None:
        pass