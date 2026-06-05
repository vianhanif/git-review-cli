from git_review_cli.formatters.markdown import MarkdownFormatter


def test_markdown_basic():
    fmt = MarkdownFormatter()
    info = {
        "iid": 42,
        "title": "Fix login bug",
        "author": {"name": "Jane Doe"},
        "state": "opened",
        "source_branch": "fix/login",
        "target_branch": "main",
        "created_at": "2026-01-01",
        "updated_at": "2026-01-02",
        "web_url": "https://gitlab.com/org/repo/-/merge_requests/42",
        "description": "Fixes the login redirect loop.",
    }
    diff = [
        {
            "new_path": "src/login.py",
            "additions": 10,
            "deletions": 2,
            "new_file": False,
            "deleted_file": False,
            "renamed_file": False,
        },
    ]
    commits = [{"short_id": "def67890", "title": "fix: login bug", "author_name": "Jane Doe"}]

    result = fmt.format(info, diff, commits, [], None, "42", "main", "standard", None, None)

    assert "MR !42" in result
    assert "Fix login bug" in result
    assert "Jane Doe" in result
    assert "src/login.py" in result
    assert "+10/-2" in result
    assert "Commits" in result


def test_markdown_caveman_skips_commits():
    fmt = MarkdownFormatter()
    info = {"iid": 1, "title": "T", "author": {"name": "A"}, "state": "o", "source_branch": "f", "target_branch": "m", "created_at": "d", "updated_at": "d", "web_url": "u", "description": ""}
    commits = [{"short_id": "abc", "title": "commit", "author_name": "A"}]

    result = fmt.format(info, [], commits, [], None, "1", "main", "caveman", None, None)

    assert "Commits" not in result


def test_markdown_deep_includes_findings():
    fmt = MarkdownFormatter()
    info = {"iid": 1, "title": "T", "author": {"name": "A"}, "state": "o", "source_branch": "f", "target_branch": "m", "created_at": "d", "updated_at": "d", "web_url": "u", "description": ""}
    findings = {
        "large_changes": [("src/big.py", 250, 0)],
        "config_changes": [],
        "test_changes": [],
        "other_changes": [],
        "has_tests": False,
        "_total_files": 1,
    }

    result = fmt.format(info, [], [], [], None, "1", "main", "deep", None, None, findings)

    assert "Findings & Observations" in result
    assert "Large Changes" in result
    assert "Missing Tests" in result


def test_markdown_empty_diff_shows_message():
    fmt = MarkdownFormatter()
    info = {"iid": 1, "title": "T", "author": {"name": "A"}, "state": "o", "source_branch": "f", "target_branch": "m", "created_at": "d", "updated_at": "d", "web_url": "u", "description": ""}

    result = fmt.format(info, [], [], [], None, "1", "main", "standard", None, None)

    assert "Could not fetch diff data" in result


def test_markdown_description_stripping():
    fmt = MarkdownFormatter()
    info = {"iid": 1, "title": "T", "author": {"name": "A"}, "state": "o", "source_branch": "f", "target_branch": "m", "created_at": "d", "updated_at": "d", "web_url": "u", "description": "\n\n  Clean description  \n\n"}

    result = fmt.format(info, [], [], [], None, "1", "main", "standard", None, None)

    assert "Clean description" in result
