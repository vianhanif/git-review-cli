import argparse
import re
import sys
import textwrap

from .git import eprint, find_project_dir, checkout_mr, get_local_diff
from .providers.base import BaseProvider
from .analyzers.patterns import analyze_patterns
from .formatters.markdown import MarkdownFormatter
from .formatters.json import JsonFormatter
from .__version__ import __version__


def _parse_input(raw: str) -> tuple[BaseProvider, str, str]:
    result = BaseProvider.resolve_from_url(raw)
    if result:
        return result
    if re.match(r"^\d+$", raw.strip()):
        mr_id = raw.strip()
        result = BaseProvider.resolve_from_remote()
        if not result:
            eprint("Error: could not detect repo from git remote")
            eprint("Use a full URL instead:")
            eprint("  git-review-cli https://gitlab.com/org/project/-/merge_requests/N")
            sys.exit(1)
        return result[0], result[1], mr_id
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

    provider, repo, mr_id = _parse_input(args.input)

    eprint(f"Fetching MR !{mr_id} from {repo}...")
    info = provider.fetch_mr_info(repo, mr_id)
    base_branch = args.base or info.get("target_branch", "main")
    diff_data = provider.fetch_mr_diff(repo, mr_id)
    commits = provider.fetch_mr_commits(repo, mr_id)
    notes = provider.fetch_mr_notes(repo, mr_id)

    commit_shas = [c.get("id", "") for c in commits if c.get("id")]

    project_dir = find_project_dir(repo)
    if project_dir:
        eprint(f"Found local clone: {project_dir}")
        eprint(f"Checking out MR branch (base: {base_branch})...")
        checkout_mr(project_dir, mr_id, base_branch, provider.fetch_ref_template)

        if not diff_data:
            eprint("API diff empty — falling back to local git diff...")
            diff_data = get_local_diff(project_dir, mr_id, base_branch)
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
        mr_number=mr_id,
        base_branch=base_branch,
        depth=depth,
        review_file=args.post,
        mr_commits_sha=commit_shas,
        findings=findings,
    )
    print(output)

    if args.post:
        provider.post_review(repo, mr_id, args.post)


if __name__ == "__main__":
    main()
