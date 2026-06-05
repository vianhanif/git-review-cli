import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from src.git import run, eprint
from .base import BaseProvider


def _find_glab() -> Optional[str]:
    for path in os.environ.get("PATH", "").split(":"):
        candidate = Path(path) / "glab"
        if candidate.exists():
            return str(candidate.resolve())
    fallback = Path.home() / ".local" / "bin" / "glab"
    if fallback.exists():
        return str(fallback)
    return None


def _glab(args: list[str], timeout: int = 30):
    glab_bin = _find_glab()
    if not glab_bin:
        eprint("Error: glab not found")
        eprint("Install: brew install glab  or  visit https://glab-cli.dev")
        sys.exit(2)
    return run([glab_bin] + args, timeout=timeout)


class GitLabProvider(BaseProvider):
    url_pattern = re.compile(
        r"^https?://gitlab\.com/(.+?)/-/merge_requests/(\d+)(?:/.*)?$"
    )

    @property
    def fetch_ref_template(self) -> str:
        return "merge-requests/{id}/head"

    @classmethod
    def _extract_remote_repo(cls, remote_url: str) -> Optional[str]:
        m = re.search(r"gitlab\.com[:/](.+?)\.git$", remote_url)
        if m:
            return m.group(1)
        m = re.search(r"gitlab\.com/(.+?)$", remote_url)
        if m:
            return m.group(1).rstrip("/")
        return None
    def fetch_mr_info(self, repo: str, mr_number: str) -> dict:
        encoded = repo.replace("/", "%2F")
        r = _glab(
            ["api", f"projects/{encoded}/merge_requests/{mr_number}"],
            timeout=15,
        )
        if r.returncode != 0:
            eprint(f"Error: glab api failed: {r.stderr.strip()}")
            sys.exit(3)
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError as e:
            eprint(f"Error: could not parse MR response: {e}")
            eprint(r.stdout[:500])
            sys.exit(3)

    def fetch_mr_diff(self, repo: str, mr_number: str) -> list[dict]:
        encoded = repo.replace("/", "%2F")
        r = _glab(
            ["api", f"projects/{encoded}/merge_requests/{mr_number}/diffs", "--paginate"],
            timeout=30,
        )
        if r.returncode != 0:
            eprint(f"Warning: glab diff API failed: {r.stderr.strip()}")
            return []
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return []

    def fetch_mr_commits(self, repo: str, mr_number: str) -> list[dict]:
        encoded = repo.replace("/", "%2F")
        r = _glab(
            ["api", f"projects/{encoded}/merge_requests/{mr_number}/commits"],
            timeout=15,
        )
        if r.returncode != 0:
            return []
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return []

    def fetch_mr_notes(self, repo: str, mr_number: str) -> list[dict]:
        encoded = repo.replace("/", "%2F")
        r = _glab(
            ["api", f"projects/{encoded}/merge_requests/{mr_number}/notes"],
            timeout=15,
        )
        if r.returncode != 0:
            return []
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return []

    def post_review(self, repo: str, mr_number: str, filepath: str) -> None:
        glab_bin = _find_glab()
        if not glab_bin:
            eprint("Error: glab not found — cannot post review")
            sys.exit(4)
        r = run(
            [glab_bin, "mr", "note", mr_number, "-R", repo, "-F", filepath],
            timeout=30,
        )
        if r.returncode != 0:
            eprint(f"Error: failed to post review: {r.stderr.strip()}")
            sys.exit(4)
        print(r.stdout.strip())
        eprint(f"Review posted to MR !{mr_number} in {repo}")
