import re
from abc import ABC, abstractmethod
from typing import Optional

from ..git import run


class BaseProvider(ABC):
    url_pattern: re.Pattern

    @abstractmethod
    def fetch_mr_info(self, repo: str, mr_id: str) -> dict: ...

    @abstractmethod
    def fetch_mr_diff(self, repo: str, mr_id: str) -> list[dict]: ...

    @abstractmethod
    def fetch_mr_commits(self, repo: str, mr_id: str) -> list[dict]: ...

    @abstractmethod
    def fetch_mr_notes(self, repo: str, mr_id: str) -> list[dict]: ...

    @abstractmethod
    def post_review(self, repo: str, mr_id: str, filepath: str) -> None: ...

    @property
    @abstractmethod
    def fetch_ref_template(self) -> str:
        """Git fetch ref pattern. GitLab: 'merge-requests/{id}/head', GitHub: 'pull/{id}/head'."""
        ...

    @classmethod
    def match_url(cls, raw: str) -> Optional[tuple[str, str]]:
        """Return (repo, mr_id) if the URL matches this provider, else None."""
        m = cls.url_pattern.match(raw.strip())
        if m:
            return m.group(1), m.group(2)
        return None

    @classmethod
    def match_remote(cls) -> Optional[str]:
        """Return repo slug if current git remote matches this provider, else None."""
        r = run(["git", "remote", "get-url", "origin"])
        if r.returncode != 0:
            return None
        return cls._extract_remote_repo(r.stdout.strip())

    @classmethod
    @abstractmethod
    def _extract_remote_repo(cls, remote_url: str) -> Optional[str]: ...

    @staticmethod
    def resolve(repo: str, platform: Optional[str] = None) -> "BaseProvider":
        if platform is None:
            platform = "gitlab"
        if platform == "gitlab":
            from .gitlab import GitLabProvider
            return GitLabProvider()
        raise ValueError(f"Unsupported platform: {platform}")

    @classmethod
    def resolve_from_remote(cls) -> Optional[tuple["BaseProvider", str]]:
        from .gitlab import GitLabProvider
        repo = GitLabProvider.match_remote()
        if repo:
            return GitLabProvider(), repo
        return None

    @classmethod
    def resolve_from_url(cls, raw: str) -> Optional[tuple["BaseProvider", str, str]]:
        from .gitlab import GitLabProvider
        for p in [GitLabProvider]:
            result = p.match_url(raw)
            if result:
                return p(), result[0], result[1]
        return None
