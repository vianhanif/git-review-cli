from typing import Optional

from src.analyzers.ownership import check_file_ownership
from src.analyzers.patterns import is_excluded
from .base import BaseFormatter


def _count_additions(f: dict) -> int:
    if f.get("additions") is not None:
        return f["additions"]
    return f.get("diff", "").count("\n+") if f.get("diff") else 0


def _count_deletions(f: dict) -> int:
    if f.get("deletions") is not None:
        return f["deletions"]
    return f.get("diff", "").count("\n-") if f.get("diff") else 0


def _format_mr_info(info: dict) -> str:
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
        desc_lines = description.split("\n")
        while desc_lines and not desc_lines[0].strip():
            desc_lines.pop(0)
        while desc_lines and not desc_lines[-1].strip():
            desc_lines.pop()
        lines.extend(desc_lines)
        lines.append("")
    return "\n".join(lines)


def _format_commits(commits: list[dict]) -> str:
    if not commits:
        return ""
    lines = ["## Commits", ""]
    for c in commits:
        sha = c.get("short_id", c.get("id", "?"))[:8]
        msg = c.get("title", "?")
        author = c.get("author_name", "?")
        lines.append(f"- `{sha}` {msg} ({author})")
    lines.append("")
    return "\n".join(lines)


def _format_changed_files(
    diff_data: list[dict],
    project_dir: Optional[str],
    mr_number: str,
    base_branch: str,
    mr_commits_sha: Optional[list[str]],
) -> str:
    lines = ["## Changed Files", ""]
    if not diff_data:
        lines.append("_Could not fetch diff data from API._")
        lines.append("")
        return "\n".join(lines)

    lines.append("| File | Changes | Owned by MR |")
    lines.append("|------|---------|-------------|")

    owned = 0
    not_owned = 0
    excluded = 0

    for f in diff_data:
        filepath = f.get("new_path", f.get("old_path", "?"))
        additions = _count_additions(f)
        deletions = _count_deletions(f)
        new_file = f.get("new_file", False)
        deleted_file = f.get("deleted_file", False)
        renamed_file = f.get("renamed_file", False)

        if is_excluded(filepath):
            status = "\U0001f6ab excluded"
            excluded += 1
        elif project_dir:
            commit_count = check_file_ownership(
                project_dir, mr_number, filepath, base_branch, mr_commits_sha
            )
            if commit_count > 0:
                status = f"\u2705 {commit_count} commit(s)"
                owned += 1
            else:
                status = "\u26a0\ufe0f not owned (branch drift)"
                not_owned += 1
        else:
            status = "\u2014"
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

    lines.append("")
    total = len(diff_data)
    lines.append(
        f"_{total} files: {owned} owned, {not_owned} not owned, {excluded} excluded_"
    )
    lines.append("")
    return "\n".join(lines)


def _format_findings(findings: Optional[dict]) -> str:
    if not findings:
        return ""
    lines = ["## Findings & Observations", ""]

    large: list = findings.get("large_changes", [])
    config: list = findings.get("config_changes", [])
    test_changes: list = findings.get("test_changes", [])
    other: list = findings.get("other_changes", [])

    if large:
        lines.append("### Large Changes (>200 lines)")
        lines.append("")
        for path, adds, dels in large:
            lines.append(f"- `{path}`: +{adds}/-{dels}")
        lines.append("")

    if config:
        lines.append("### Configuration / Infra Changes")
        lines.append("")
        for path, adds, dels in config:
            lines.append(f"- `{path}`: +{adds}/-{dels}")
        lines.append("")

    if not test_changes and (large or len(findings.get("_total_files", 0) or []) > 3):
        lines.append("### Missing Tests")
        lines.append("")
        lines.append("No test files detected in this MR. Consider adding test coverage.")
        lines.append("")

    outlines = (
        [(f"`{p}`: +{a}/-{d}") for p, a, d in test_changes]
        + [(f"`{p}`: +{a}/-{d}") for p, a, d in other]
    )
    if outlines:
        lines.append("### All Changes")
        lines.append("")
        for line in outlines:
            lines.append(f"- {line}")
        lines.append("")

    return "\n".join(lines)


def _format_notes(notes: list[dict]) -> str:
    if not notes:
        return ""
    user_notes = [n for n in notes if not n.get("system", False)]
    if not user_notes:
        return ""
    lines = ["## Existing Comments", ""]
    lines.append(f"_{len(user_notes)} non-system comments on MR_")
    lines.append("")
    return "\n".join(lines)


def _format_review_section(review_file: Optional[str]) -> str:
    if not review_file:
        return ""
    lines = ["## Review Post", ""]
    try:
        with open(review_file) as f:
            content = f.read()
        lines.append(content)
    except (IOError, OSError) as e:
        lines.append(f"_Could not read review file: {e}_")
    lines.append("")
    return "\n".join(lines)


class MarkdownFormatter(BaseFormatter):
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
        parts = []
        parts.append(_format_mr_info(info))

        if depth != "caveman":
            parts.append(_format_commits(commits))

        parts.append(
            _format_changed_files(
                diff_data, project_dir, mr_number, base_branch, mr_commits_sha
            )
        )

        if depth == "deep":
            parts.append(_format_findings(findings))

        parts.append(_format_notes(notes))
        parts.append(_format_review_section(review_file))

        return "\n".join(parts)
