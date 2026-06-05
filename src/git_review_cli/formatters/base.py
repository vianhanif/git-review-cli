from abc import ABC, abstractmethod
from typing import Optional


class BaseFormatter(ABC):
    @abstractmethod
    def format(
        self,
        info: dict,
        diff_data: list[dict],
        commits: list[dict],
        notes: list[dict],
        project_dir: Optional[str],
        mr_number: str,
        base_branch: str,
        depth: str,
        review_file: Optional[str],
        mr_commits_sha: Optional[list[str]],
        findings: Optional[dict] = None,
    ) -> str: ...
