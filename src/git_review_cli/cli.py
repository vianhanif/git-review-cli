import argparse
import re
import sys
import textwrap
from typing import Optional

from .__version__ import __version__
from .git import eprint, run, find_project_dir, checkout_mr, get_local_diff
from .providers.base import BaseProvider
from .analyzers.patterns import analyze_patterns
from .formatters.markdown import MarkdownFormatter
from .formatters.json import JsonFormatter

URL_PATTERN = re.compile(
    r"^https?://gitlab\.com/(.+?)/-/merge_requests/(\d+)(?:/.*)?$"
)


def _detect_repo_from_git() -> Optional[str]:
    r = run(["git", "remote", "get-url", "origin"])
    if r.returncode != 0:
        return None
    url = r.stdout.strip()
    m = re.search(r"gitlab\.com[:/](.+?)\.git$", url)
    if m:
        return m.group(1)
    m = re.search(r"gitlab\.com/(.+?)$", url)
    if m:
        return m.group(1).rstrip("/")
    return None


def _parse_input(raw: str) -> tuple[str, str]:
    m = URL_PATTERN.match(raw.strip())
    if m:
        return m.group(1), m.group(2)
    if re.match(r"^\d+$", raw.strip()):
        mr_number = raw.strip()
        repo = _detect_repo_from_git()
        if not repo:
            eprint("Error: could not detect repo from git remote")
            eprint("Use a full URL instead:")
            eprint("  git-review-cli https://gitlab.com/org/project/-/merge_requests/N")
            sys.exit(1)
        return repo, mr_number
    eprint(f"Error: unrecognised input: {raw}")
    eprint("Expected: https://gitlab.com/org/project/-/merge_requests/N  or  <MR-number>")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Review GitLab merge requests from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(f"""\
            Examples:
              git-review-cli https://gitlab.com/org/project/-/merge_requests/123
              git-review-cli 123 --caveman
              git-review-cli 123 --deep
              git-review-cli 123 --json

              cat > /tmp/review.md << 'REVIEW'
              ## Review findings
              - Looks good
              REVIEW
              git-review-cli 123 --post /tmp/review.md

            version: {__version__}
        """),
    )
    parser.add_argument(
        "input",
        help="GitLab MR URL or MR number (shorthand, uses current repo)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    parser.add_argument("--caveman", action="store_true", help="Concise output")
    parser.add_argument("--deep", action="store_true", help="Deep analysis with findings")
    parser.add_argument("--post", metavar="FILE", help="Post review file to the MR")
    parser.add_argument("--base", metavar="BRANCH", help="Override base branch")
    parser.add_argument("--version", action="version", version=f"git-review-cli {__version__}")

    args = parser.parse_args()

    if args.caveman and args.deep:
        eprint("Error: --caveman and --deep are mutually exclusive")
        sys.exit(1)
    depth = "deep" if args.deep else ("caveman" if args.caveman else "standard")

    repo, mr_number = _parse_input(args.input)

    provider = BaseProvider.resolve(repo)
    eprint(f"Fetching MR !{mr_number} from {repo}...")

    info = provider.fetch_mr_info(repo, mr_number)
    base_branch = args.base or info.get("target_branch", "main")
    diff_data = provider.fetch_mr_diff(repo, mr_number)
    commits = provider.fetch_mr_commits(repo, mr_number)
    notes = provider.fetch_mr_notes(repo, mr_number)

    commit_shas = [c.get("id", "") for c in commits if c.get("id")]

    project_dir = find_project_dir(repo)
    if project_dir:
        eprint(f"Found local clone: {project_dir}")
        eprint(f"Checking out MR branch (base: {base_branch})...")
        checkout_mr(project_dir, mr_number, base_branch)

        if not diff_data:
            eprint("API diff empty — falling back to local git diff...")
            diff_data = get_local_diff(project_dir, mr_number, base_branch)
    else:
        eprint("No local clone found — skipping ownership verification")

    findings = None
    if depth == "deep":
        findings = analyze_patterns(diff_data)
        findings["_total_files"] = len(diff_data)

    if args.as_json:
        formatter = JsonFormatter()
    else:
        formatter = MarkdownFormatter()

    output = formatter.format(
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
        findings=findings,
    )
    print(output)

    if args.post:
        provider.post_review(repo, mr_number, args.post)


if __name__ == "__main__":
    main()
