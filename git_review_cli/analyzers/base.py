from abc import ABC, abstractmethod


class BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(self, diff_data: list[dict], **kwargs) -> dict: ...
