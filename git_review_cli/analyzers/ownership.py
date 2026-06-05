from typing import Optional

from ..git import run_in_project


_TOUCHED_CACHE: dict[str, dict[str, int]] = {}


def get_mr_touched_files(
    project_dir: str,
    mr_number: str,
    base_branch: str,
    mr_commits: Optional[list[str]] = None,
) -> dict[str, int]:
    branch = f"mr-{mr_number}"
    current_branch = ""
    cb_r = run_in_project(project_dir, ["git", "branch", "--show-current"])
    if cb_r.returncode == 0:
        current_branch = cb_r.stdout.strip()
    range_ref = "HEAD" if current_branch or current_branch == branch else branch

    r = run_in_project(
        project_dir,
        ["git", "diff", "--name-only", f"origin/{base_branch}...{range_ref}"],
        timeout=30,
    )
    result: dict[str, int] = {}
    if r.returncode == 0:
        for f in r.stdout.strip().split("\n"):
            f = f.strip()
            if f:
                result[f] = result.get(f, 0) + 1
    if result:
        return result

    if mr_commits:
        for sha in mr_commits:
            dr = run_in_project(
                project_dir,
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
                timeout=15,
            )
            if dr.returncode == 0:
                for f in dr.stdout.strip().split("\n"):
                    f = f.strip()
                    if f:
                        result[f] = result.get(f, 0) + 1
    return result


def check_file_ownership(
    project_dir: str,
    mr_number: str,
    filepath: str,
    base_branch: str,
    mr_commits: Optional[list[str]] = None,
) -> int:
    global _TOUCHED_CACHE
    cache_key = f"{project_dir}:{mr_number}:{base_branch}"
    if cache_key not in _TOUCHED_CACHE:
        _TOUCHED_CACHE[cache_key] = get_mr_touched_files(
            project_dir, mr_number, base_branch, mr_commits
        )
    return _TOUCHED_CACHE[cache_key].get(filepath, 0)
