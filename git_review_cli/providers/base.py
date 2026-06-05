from abc import ABC, abstractmethod
from typing import Optional


class BaseProvider(ABC):
    @abstractmethod
    def fetch_mr_info(self, repo: str, mr_number: str) -> dict: ...

    @abstractmethod
    def fetch_mr_diff(self, repo: str, mr_number: str) -> list[dict]: ...

    @abstractmethod
    def fetch_mr_commits(self, repo: str, mr_number: str) -> list[dict]: ...

    @abstractmethod
    def fetch_mr_notes(self, repo: str, mr_number: str) -> list[dict]: ...

    @abstractmethod
    def post_review(self, repo: str, mr_number: str, filepath: str) -> None: ...

    @staticmethod
    def resolve(repo: str, platform: Optional[str] = None) -> "BaseProvider":
        if platform is None:
            platform = _detect_platform(repo)
        if platform == "gitlab":
            from .gitlab import GitLabProvider
            return GitLabProvider()
        raise ValueError(f"Unsupported platform: {platform}")


def _detect_platform(repo: str) -> str:
    return "gitlab"
