#!/usr/bin/env python3
"""
opencode-glab-review — Standardized GitLab MR data gatherer for opencode.

Parses a GitLab MR URL (or MR number), fetches all relevant data,
and outputs structured information for opencode to consume.

Usage:
    opencode-glab-review <gitlab-url>
    opencode-glab-review <gitlab-url> --json          # machine-readable output
    opencode-glab-review <gitlab-url> --caveman        # concise output
    opencode-glab-review <gitlab-url> --post <file>    # post a review note
    opencode-glab-review 8328                          # shorthand (current repo)
    opencode-glab-review 8328 --caveman

Exit codes:
    0  — success
    1  — usage / parse error
    2  — glab not found
    3  — git operation failed
    4  — posting failed
"""

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Optional

# ─── constants ───────────────────────────────────────────────────────────────

__version__ = "1.0.0"

EXCLUDED_FILES = {
    "package-lock.json",
    "yarn.lock",
    ".npmrc",
    "go.sum",
    "go.mod",
}

URL_PATTERN = re.compile(
    r"^https?://gitlab\.com/(.+?)/-/merge_requests/(\d+)(?:/.*)?$"
)

GITLAB_HOST = "gitlab.com"

# ─── helpers ─────────────────────────────────────────────────────────────────


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=kwargs.pop("timeout", 60),
        **kwargs,
    )


def find_glab() -> Optional[str]:
    """Locate glab binary. Checks PATH and ~/.local/bin."""
    for path in os.environ.get("PATH", "").split(":"):
        candidate = Path(path) / "glab"
        if candidate.exists():
            return str(candidate.resolve())
    fallback = Path.home() / ".local" / "bin" / "glab"
    if fallback.exists():
        return str(fallback)
    return None


def find_project_dir(repo: str) -> Optional[str]:
    """Find a local clone of the given repo under ~/Documents/alvian/."""
    base = Path.home() / "Documents" / "alvian"
    if not base.exists():
        return None
    project_name = repo.split("/")[-1]
    for d in base.iterdir():
        if d.is_dir() and d.name == project_name:
            git_dir = d / ".git"
            if git_dir.exists() or (d / "HEAD").exists():
                return str(d)
    return None


def run_in_project_dir(project_dir: str, args: list[str], **kwargs):
    """Run a shell command in the project directory directly via subprocess."""
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=kwargs.pop("timeout", 60),
        cwd=project_dir,
        **kwargs,
    )


# ─── URL / input parsing ─────────────────────────────────────────────────────


def parse_input(raw: str) -> tuple[str, str]:
    """Return (repo, mr_number) from a URL or shorthand MR number."""
    m = URL_PATTERN.match(raw.strip())
    if m:
        return m.group(1), m.group(2)
    # Shorthand: just a number — detect repo from git remote
    if re.match(r"^\d+$", raw.strip()):
        mr_number = raw.strip()
        repo = detect_repo_from_git()
        if not repo:
            eprint("Error: could not detect repo from git remote")
            eprint("Use a full URL instead:")
            eprint("  opencode-glab-review https://gitlab.com/org/project/-/merge_requests/N")
            sys.exit(1)
        return repo, mr_number
    eprint(f"Error: unrecognised input: {raw}")
    eprint("Expected: https://gitlab.com/org/project/-/merge_requests/N  or  <MR-number>")
    sys.exit(1)


def detect_repo_from_git() -> Optional[str]:
    """Get the GitLab repo slug from the current directory's git remote."""
    r = run(["git", "remote", "get-url", "origin"])
    if r.returncode != 0:
        return None
    url = r.stdout.strip()
    # Handle git@gitlab.com:org/project.git and https://gitlab.com/org/project
    m = re.search(r"gitlab\.com[:/](.+?)\.git$", url)
    if m:
        return m.group(1)
    m = re.search(r"gitlab\.com/(.+?)$", url)
    if m:
        return m.group(1).rstrip("/")
    return None


# ─── glab operations ─────────────────────────────────────────────────────────


def glab(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run glab with the given args."""
    glab_bin = find_glab()
    if not glab_bin:
        eprint("Error: glab not found")
        eprint("Install: brew install glab  or  visit https://glab-cli.dev")
        sys.exit(2)
    return run([glab_bin] + args, timeout=timeout)


def fetch_mr_info(repo: str, mr_number: str) -> dict:
    """Fetch MR metadata as JSON via glab API."""
    encoded = repo.replace("/", "%2F")
    r = glab(
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


def fetch_mr_diff(repo: str, mr_number: str) -> list[dict]:
    """Fetch MR diff as JSON list via glab API."""
    encoded = repo.replace("/", "%2F")
    r = glab(
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


def fetch_mr_commits(repo: str, mr_number: str) -> list[dict]:
    """Fetch MR commits as JSON via glab API."""
    encoded = repo.replace("/", "%2F")
    r = glab(
        ["api", f"projects/{encoded}/merge_requests/{mr_number}/commits"],
        timeout=15,
    )
    if r.returncode != 0:
        return []
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return []


def fetch_mr_notes(repo: str, mr_number: str) -> list[dict]:
    """Fetch MR notes/comments via glab API."""
    encoded = repo.replace("/", "%2F")
    r = glab(
        ["api", f"projects/{encoded}/merge_requests/{mr_number}/notes"],
        timeout=15,
    )
    if r.returncode != 0:
        return []
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return []


# ─── git / local operations ──────────────────────────────────────────────────


def checkout_mr_locally(project_dir: str, mr_number: str, base_branch: str) -> bool:
    """Fetch and checkout the MR branch locally. Returns True on success."""
    branch = f"mr-{mr_number}"

    # First check if branch is already checked out (cannot fetch into checked out branch)
    r = run_in_project_dir(project_dir, ["git", "branch", "--show-current"])
    currently_on = r.stdout.strip() if r.returncode == 0 else ""

    if currently_on == branch:
        # Branch is checked out — fetch into FETCH_HEAD and merge
        r1 = run_in_project_dir(
            project_dir,
            [
                "git",
                "fetch",
                "--force",
                "origin",
                f"merge-requests/{mr_number}/head",
            ],
        )
        if r1.returncode != 0:
            # Fetch failed — maybe already up to date, that's OK
            pass
        return True

    # Normal case: branch not checked out
    r1 = run_in_project_dir(
        project_dir,
        [
            "git",
            "fetch",
            "--force",
            "origin",
            f"merge-requests/{mr_number}/head:{branch}",
        ],
    )
    if r1.returncode != 0:
        eprint(f"Warning: git fetch for MR {mr_number} failed: {r1.stderr.strip()}")
        return False
    r2 = run_in_project_dir(project_dir, ["git", "checkout", branch, "--quiet"])
    if r2.returncode != 0:
        eprint(f"Warning: git checkout {branch} failed: {r2.stderr.strip()}")
        return False
    return True


def get_mr_touched_files(
    project_dir: str,
    mr_number: str,
    base_branch: str,
    mr_commits: Optional[list[str]] = None,
) -> dict[str, int]:
    """Get a dict of {filepath: commit_count} for all files touched by MR commits.

    Strategy:
    1. Three-dot diff against base branch (works for open MRs).
    2. If empty and we have MR commits, check each commit via git diff-tree
       (works for merged MRs where the branch is already in the target).
    """

    branch = f"mr-{mr_number}"
    current_branch = ""

    cb_r = run_in_project_dir(project_dir, ["git", "branch", "--show-current"])
    if cb_r.returncode == 0:
        current_branch = cb_r.stdout.strip()

    range_ref = "HEAD" if current_branch or current_branch == branch else branch

    # Strategy 1: three-dot diff
    r = run_in_project_dir(
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

    # Strategy 2: check each MR commit via diff-tree (merged MRs)
    if mr_commits:
        for sha in mr_commits:
            dr = run_in_project_dir(
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


MR_TOUCHED_CACHE: dict[str, dict[str, int]] = {}


def check_file_ownership(
    project_dir: str,
    mr_number: str,
    filepath: str,
    base_branch: str,
    mr_commits: Optional[list[str]] = None,
) -> int:
    """Check how many MR commits touched a file. Uses cached batch result."""
    global MR_TOUCHED_CACHE
    cache_key = f"{project_dir}:{mr_number}:{base_branch}"

    if cache_key not in MR_TOUCHED_CACHE:
        MR_TOUCHED_CACHE[cache_key] = get_mr_touched_files(
            project_dir, mr_number, base_branch, mr_commits
        )

    return MR_TOUCHED_CACHE[cache_key].get(filepath, 0)


# ─── formatting ──────────────────────────────────────────────────────────────


def format_mr_info(info: dict) -> str:
    """Format MR metadata into human-readable block."""
    lines = []
    lines.append(f"# MR !{info.get('iid', '?')} — {info.get('title', 'Untitled')}")
    lines.append("")
    lines.append(f"- **Author:** {info.get('author', {}).get('name', 'Unknown')}")
    lines.append(f"- **State:** {info.get('state', 'unknown')}")
    lines.append(f"- **Source branch:** `{info.get('source_branch', '?')}`")
    lines.append(f"- **Target branch:** `{info.get('target_branch', '?')}`")
    lines.append(f"- **Created:** {info.get('created_at', '?')}")
    lines.append(f"- **Updated:** {info.get('updated_at', '?')}")
    lines.append(f"- **URL:** {info.get('web_url', '?')}")
    lines.append("")
    description = info.get("description", "").strip()
    if description:
        lines.append("### Description")
        lines.append("")
        # Strip leading/trailing blank lines from description
        desc_lines = description.split("\n")
        while desc_lines and not desc_lines[0].strip():
            desc_lines.pop(0)
        while desc_lines and not desc_lines[-1].strip():
            desc_lines.pop()
        lines.extend(desc_lines)
        lines.append("")
    return "\n".join(lines)


def format_changed_files(
    diff_data: list[dict],
    project_dir: Optional[str],
    mr_number: str,
    base_branch: str,
    depth: str,
    mr_commits_sha: Optional[list[str]] = None,
) -> str:
    """Format the list of changed files with ownership verification."""
    lines = []
    lines.append("## Changed Files")
    lines.append("")

    if not diff_data:
        lines.append("_Could not fetch diff data from API._")
        lines.append("")
        return "\n".join(lines)

    # Build a compact table
    lines.append("| File | Changes | Owned by MR |")
    lines.append("|------|---------|-------------|")

    owned = 0
    not_owned = 0
    excluded = 0

    for f in diff_data:
        filepath = f.get("new_path", f.get("old_path", "?"))
        additions = f.get("additions", 0) or (f.get("diff", "").count("\n+") if f.get("diff") else 0)
        deletions = f.get("deletions", 0) or (f.get("diff", "").count("\n-") if f.get("diff") else 0)
        new_file = f.get("new_file", False)
        deleted_file = f.get("deleted_file", False)
        renamed_file = f.get("renamed_file", False)

        # Check exclusion
        basename = os.path.basename(filepath)
        if basename in EXCLUDED_FILES or any(
            filepath.endswith(s) for s in [".sum", ".png", ".jpg", ".ico"]
        ):
            status = "🚫 excluded"
            excluded += 1
        elif project_dir:
            commit_count = check_file_ownership(
                project_dir, mr_number, filepath, base_branch, mr_commits_sha
            )
            if commit_count > 0:
                status = f"✅ {commit_count} commit(s)"
                owned += 1
            else:
                status = "⚠️ not owned (branch drift)"
                not_owned += 1
        else:
            status = "—"
            owned += 1

        change_type = ""
        if new_file:
            change_type = " (new)"
        elif deleted_file:
            change_type = " (del)"
        elif renamed_file:
            change_type = " (ren)"

        lines.append(
            f"| `{filepath}{change_type}` | +{additions}/-{deletions} | {status} |"
        )

    # Summary
    lines.append("")
    total = len(diff_data)
    lines.append(
        f"_{total} files: {owned} owned, {not_owned} not owned, {excluded} excluded_"
    )
    lines.append("")

    return "\n".join(lines)


def format_commits(commits: list[dict], depth: str) -> str:
    """Format the commit list."""
    if not commits:
        return ""

    lines = []
    lines.append("## Commits")
    lines.append("")
    for c in commits:
        sha = c.get("short_id", c.get("id", "?"))[:8]
        msg = c.get("title", "?")
        author = c.get("author_name", "?")
        lines.append(f"- `{sha}` {msg} ({author})")
    lines.append("")
    return "\n".join(lines)


def format_notes(notes: list[dict]) -> str:
    """Format existing MR notes/comments (summary only)."""
    if not notes:
        return ""

    # Filter out system notes
    user_notes = [n for n in notes if not n.get("system", False)]
    if not user_notes:
        return ""

    lines = []
    lines.append("## Existing Comments")
    lines.append("")
    lines.append(f"_{len(user_notes)} non-system comments on MR_")
    lines.append("")
    return "\n".join(lines)


def format_findings(
    diff_data: list[dict],
    project_dir: Optional[str],
    mr_number: str,
    base_branch: str,
    depth: str,
) -> str:
    """Generate a findings section based on diff analysis."""
    lines = []
    lines.append("## Findings & Observations")
    lines.append("")

    large_changes = []
    config_changes = []
    test_changes = []
    other_changes = []

    config_patterns = (
        ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini", ".env",
        "docker-compose", "Dockerfile", "Makefile",
    )

    for f in diff_data:
        filepath = f.get("new_path", f.get("old_path", "?"))
        additions = f.get("diff", "").count("\n+") if f.get("diff") else 0
        deletions = f.get("diff", "").count("\n-") if f.get("diff") else 0
        total = additions + deletions

        basename = os.path.basename(filepath)
        if basename in EXCLUDED_FILES:
            continue

        entry = (filepath, additions, deletions)

        if "test" in filepath.lower() or "spec" in filepath.lower():
            test_changes.append(entry)
        elif any(filepath.endswith(p) or basename == p.lstrip(".") for p in config_patterns):
            config_changes.append(entry)
        elif total > 200:
            large_changes.append(entry)
        else:
            other_changes.append(entry)

    if large_changes:
        lines.append("### Large Changes (>200 lines)")
        lines.append("")
        for path, adds, dels in large_changes:
            lines.append(f"- `{path}`: +{adds}/-{dels}")
        lines.append("")

    if config_changes:
        lines.append("### Configuration / Infra Changes")
        lines.append("")
        for path, adds, dels in config_changes:
            lines.append(f"- `{path}`: +{adds}/-{dels}")
        lines.append("")

    if not test_changes and (large_changes or len(diff_data) > 3):
        lines.append("### Missing Tests")
        lines.append("")
        lines.append("No test files detected in this MR. Consider adding test coverage.")
        lines.append("")

    outlines = (
        [(f"`{p}`: +{a}/-{d}") for p, a, d in test_changes]
        + [(f"`{p}`: +{a}/-{d}") for p, a, d in other_changes]
    )
    if outlines:
        lines.append("### All Changes")
        lines.append("")
        for line in outlines:
            lines.append(f"- {line}")
        lines.append("")

    return "\n".join(lines)


def format_review_section(review_file: Optional[str]) -> str:
    """Format a section for posting a review."""
    if not review_file:
        return ""
    lines = []
    lines.append("## Review Post")
    lines.append("")
    try:
        with open(review_file) as f:
            content = f.read()
        lines.append(content)
    except (IOError, OSError) as e:
        lines.append(f"_Could not read review file: {e}_")
    lines.append("")
    return "\n".join(lines)


# ─── main ────────────────────────────────────────────────────────────────────


def build_output(
    info: dict,
    diff_data: list[dict],
    commits: list[dict],
    notes: list[dict],
    project_dir: Optional[str],
    mr_number: str,
    base_branch: str,
    depth: str,
    review_file: Optional[str],
    mr_commits_sha: Optional[list[str]] = None,
    fmt: str = "markdown",
) -> str:
    """Build the final output string."""
    if fmt == "json":
        return json.dumps(
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

    # Build markdown output
    parts = []
    parts.append(format_mr_info(info))

    if depth != "caveman":
        parts.append(format_commits(commits, depth))

    parts.append(
        format_changed_files(
            diff_data, project_dir, mr_number, base_branch, depth, mr_commits_sha
        )
    )

    if depth == "deep":
        parts.append(
            format_findings(
                diff_data, project_dir, mr_number, base_branch, depth
            )
        )

    parts.append(format_notes(notes))
    parts.append(format_review_section(review_file))

    return "\n".join(parts)


def post_review(repo: str, mr_number: str, filepath: str):
    """Post a review note to the MR using glab mr note -F."""
    glab_bin = find_glab()
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


def main():
    parser = argparse.ArgumentParser(
        description="Fetch GitLab MR details for opencode reviews",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              # Full URL — works from any directory
              opencode-glab-review https://gitlab.com/pasarpolis/operationspanel-web/-/merge_requests/4223

              # Caveman mode — concise summary (recommended for quick reviews)
              opencode-glab-review https://gitlab.com/pasarpolis/operationspanel-web/-/merge_requests/4223 --caveman

              # Deep mode — full analysis with findings per file
              opencode-glab-review https://gitlab.com/pasarpolis/operationspanel-web/-/merge_requests/4223 --deep

              # JSON output — for machine consumption
              opencode-glab-review https://gitlab.com/pasarpolis/operationspanel-web/-/merge_requests/4223 --json

              # Shorthand — auto-detects repo from current git remote
              opencode-glab-review 4223 --caveman

              # Post a review to the MR (markdown-safe via file)
              cat > /tmp/review-4223.md << 'REVIEW'
              ## Review findings
              - Looks good overall
              - One concern in src/pages/...
              REVIEW
              opencode-glab-review https://gitlab.com/pasarpolis/operationspanel-web/-/merge_requests/4223 --post /tmp/review-4223.md

            Repos tested:
              pasarpolis/operationspanel-web     — operationspanel-web
              pasarpolis/core                    — core (Go)
              pasarpolis/integrationservice      — integrationservice (Go)
        """),
    )
    parser.add_argument(
        "input",
        help="GitLab MR URL or MR number (shorthand, uses current repo)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output as JSON instead of markdown",
    )
    parser.add_argument(
        "--caveman",
        action="store_true",
        help="Concise output (caveman mode)",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Deep analysis (full flow tracing)",
    )
    parser.add_argument(
        "--post",
        metavar="FILE",
        help="Post the given review file to the MR",
    )
    parser.add_argument(
        "--base",
        metavar="BRANCH",
        help="Override base branch (default: auto-detect from MR)",
    )

    args = parser.parse_args()

    # Determine depth
    if args.caveman and args.deep:
        eprint("Error: --caveman and --deep are mutually exclusive")
        sys.exit(1)
    depth = "deep" if args.deep else ("caveman" if args.caveman else "standard")

    # Parse input
    repo, mr_number = parse_input(args.input)

    # Fetch MR data
    eprint(f"Fetching MR !{mr_number} from {repo}...")
    info = fetch_mr_info(repo, mr_number)
    base_branch = args.base or info.get("target_branch", "aus-testing")

    diff_data = fetch_mr_diff(repo, mr_number)
    commits = fetch_mr_commits(repo, mr_number)
    notes = fetch_mr_notes(repo, mr_number)

    # Extract commit SHAs early (needed for both ownership check and diff fallback)
    commit_shas = [c.get("id", "") for c in commits if c.get("id")]

    # Try to checkout locally for ownership analysis and git-based diff fallback
    project_dir = find_project_dir(repo)
    if project_dir:
        eprint(f"Found local clone: {project_dir}")
        eprint(f"Checking out MR branch (base: {base_branch})...")
        checked_out = checkout_mr_locally(project_dir, mr_number, base_branch)

        # Fallback: if API diff was empty, use git diff locally (stat only)
        if not diff_data:
            eprint("API diff empty — falling back to local git diff (stat)...")

            # Always use three-dot range — git automatically finds the merge base.
            # Explicit merge-base + two-dot range breaks for merged MRs.
            branch = f"mr-{mr_number}"
            # Check if branch exists locally
            has_branch = (
                run_in_project_dir(
                    project_dir, ["git", "rev-parse", "--verify", "--quiet", branch]
                ).returncode
                == 0
            )
            if has_branch:
                range_spec = f"origin/{base_branch}...{branch}"
            else:
                range_spec = f"origin/{base_branch}...HEAD"

            # Use --name-status for clean file list, then --numstat for counts
            # --numstat gives tab-separated: adds<TAB>dels<TAB>path   (no truncation)
            status_r = run_in_project_dir(
                project_dir,
                ["git", "diff", range_spec, "--name-status"],
                timeout=30,
            )
            numstat_r = run_in_project_dir(
                project_dir,
                ["git", "diff", range_spec, "--numstat"],
                timeout=30,
            )
            # Parse numstat output: "adds\tdels\tpath"
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
                        path = parts[2]
                        numstat_counts[path] = (adds, dels)

            if status_r.returncode == 0:
                for line in status_r.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line or len(line.split("\t")) < 2:
                        continue
                    parts = line.split("\t")
                    status = parts[0]
                    filepath = parts[-1]  # new name for renames
                    adds, dels = numstat_counts.get(filepath, (0, 0))
                    diff_data.append(
                        {
                            "new_path": filepath,
                            "old_path": parts[1] if len(parts) > 2 else filepath,
                            "additions": adds,
                            "deletions": dels,
                            "diff": "",
                            "new_file": status == "A",
                            "deleted_file": status == "D",
                            "renamed_file": status.startswith("R"),
                        }
                    )
    else:
        eprint("No local clone found — skipping ownership verification")

    # Build and print output
    output = build_output(
        info=info,
        diff_data=diff_data,
        commits=commits,
        notes=notes,
        project_dir=project_dir,
        mr_number=mr_number,
        base_branch=base_branch,
        depth=depth,
        review_file=args.post,
        mr_commits_sha=commit_shas,
        fmt="json" if args.as_json else "markdown",
    )
    print(output)

    # Post if requested
    if args.post:
        post_review(repo, mr_number, args.post)


if __name__ == "__main__":
    main()
