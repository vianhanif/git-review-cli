import json as _json
from typing import Optional

from .base import BaseFormatter


class JsonFormatter(BaseFormatter):
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
    ) -> str:
        return _json.dumps(
            {
                "mr": {
                    "number": mr_number,
                    "title": info.get("title"),
                    "author": info.get("author", {}).get("name"),
                    "state": info.get("state"),
                    "source_branch": info.get("source_branch"),
                    "target_branch": info.get("target_branch"),
                    "web_url": info.get("web_url"),
                    "description": info.get("description"),
                },
                "commits": [
                    {
                        "sha": c.get("short_id", c.get("id")),
                        "title": c.get("title"),
                        "author": c.get("author_name"),
                    }
                    for c in commits
                ],
                "files": [
                    {
                        "path": f.get("new_path", f.get("old_path")),
                        "additions": (
                            f.get("diff", "").count("\n+") if f.get("diff") else 0
                        ),
                        "deletions": (
                            f.get("diff", "").count("\n-") if f.get("diff") else 0
                        ),
                        "new_file": f.get("new_file", False),
                        "deleted_file": f.get("deleted_file", False),
                    }
                    for f in diff_data
                ],
                "base_branch": base_branch,
            },
            indent=2,
        )
