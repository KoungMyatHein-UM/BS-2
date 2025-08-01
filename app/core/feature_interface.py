from abc import ABC, abstractmethod

class BaseFeature(ABC):
    # ***** REQUIRED *****
    @abstractmethod
    def run(self, file_path: str) -> str:
        pass

    # ***** OPTIONAL *****
    def self_test(self) -> bool:
        pass

    # ***** OPTIONAL *****
    def shutdown(self) -> None:
        pass