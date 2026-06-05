import subprocess
import sys
from pathlib import Path
from typing import Optional

DEFAULT_PROJECTS_BASE = Path.cwd()


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=kwargs.pop("timeout", 60),
        **kwargs,
    )


def run_in_project(project_dir: str, args: list[str], **kwargs):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=kwargs.pop("timeout", 60),
        cwd=project_dir,
        **kwargs,
    )


def find_project_dir(repo: str, base: Optional[Path] = None) -> Optional[str]:
    if base is None:
        base = DEFAULT_PROJECTS_BASE
    if not base.exists():
        return None
    project_name = repo.split("/")[-1]
    if base.is_dir() and base.name == project_name:
        git_dir = base / ".git"
        if git_dir.exists() or (base / "HEAD").exists():
            return str(base)
    for d in base.iterdir():
        if d.is_dir() and d.name == project_name:
            git_dir = d / ".git"
            if git_dir.exists() or (d / "HEAD").exists():
                return str(d)
    return None


def checkout_mr(project_dir: str, mr_number: str, base_branch: str) -> bool:
    branch = f"mr-{mr_number}"
    r = run_in_project(project_dir, ["git", "branch", "--show-current"])
    currently_on = r.stdout.strip() if r.returncode == 0 else ""

    if currently_on == branch:
        r1 = run_in_project(
            project_dir,
            ["git", "fetch", "--force", "origin", f"merge-requests/{mr_number}/head"],
        )
        return True

    r1 = run_in_project(
        project_dir,
        ["git", "fetch", "--force", "origin", f"merge-requests/{mr_number}/head:{branch}"],
    )
    if r1.returncode != 0:
        eprint(f"Warning: git fetch for MR {mr_number} failed: {r1.stderr.strip()}")
        return False
    r2 = run_in_project(project_dir, ["git", "checkout", branch, "--quiet"])
    if r2.returncode != 0:
        eprint(f"Warning: git checkout {branch} failed: {r2.stderr.strip()}")
        return False
    return True


def get_local_diff(project_dir: str, mr_number: str, base_branch: str) -> list[dict]:
    branch = f"mr-{mr_number}"
    has_branch = (
        run_in_project(
            project_dir, ["git", "rev-parse", "--verify", "--quiet", branch]
        ).returncode
        == 0
    )
    range_spec = f"origin/{base_branch}...{branch}" if has_branch else f"origin/{base_branch}...HEAD"

    status_r = run_in_project(
        project_dir, ["git", "diff", range_spec, "--name-status"], timeout=30
    )
    numstat_r = run_in_project(
        project_dir, ["git", "diff", range_spec, "--numstat"], timeout=30
    )

    numstat_counts = {}
    if numstat_r.returncode == 0:
        for line in numstat_r.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                adds = int(parts[0]) if parts[0] != "-" else 0
                dels = int(parts[1]) if parts[1] != "-" else 0
                numstat_counts[parts[2]] = (adds, dels)

    result = []
    if status_r.returncode == 0:
        for line in status_r.stdout.strip().split("\n"):
            line = line.strip()
            if not line or len(line.split("\t")) < 2:
                continue
            parts = line.split("\t")
            status = parts[0]
            filepath = parts[-1]
            adds, dels = numstat_counts.get(filepath, (0, 0))
            result.append({
                "new_path": filepath,
                "old_path": parts[1] if len(parts) > 2 else filepath,
                "additions": adds,
                "deletions": dels,
                "diff": "",
                "new_file": status == "A",
                "deleted_file": status == "D",
                "renamed_file": status.startswith("R"),
            })
    return result
