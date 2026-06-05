from git_review_cli.formatters.json import JsonFormatter


def test_json_formatter_basic():
    fmt = JsonFormatter()
    info = {
        "title": "Test MR",
        "author": {"name": "Jane"},
        "state": "opened",
        "source_branch": "feat/x",
        "target_branch": "main",
        "web_url": "https://gitlab.com/org/repo/-/merge_requests/1",
        "description": "A test MR",
    }
    diff = [{"new_path": "src/app.py", "diff": "\n+hello\n-world", "new_file": True, "deleted_file": False}]
    commits = [{"short_id": "abc12345", "title": "feat: add app", "author_name": "Jane"}]
    notes = []

    result = fmt.format(info, diff, commits, notes, None, "1", "main", "standard", None, None)

    assert '"title": "Test MR"' in result
    assert '"number": "1"' in result
    assert '"path": "src/app.py"' in result
    assert '"additions": 1' in result
    assert '"deletions": 1' in result
    assert '"new_file": true' in result


def test_json_formatter_uses_api_additions():
    fmt = JsonFormatter()
    info = {"title": "T", "author": {"name": "J"}, "state": "o", "source_branch": "f", "target_branch": "m", "web_url": "u", "description": ""}
    diff = [{"new_path": "src/app.py", "additions": 42, "deletions": 7, "new_file": False, "deleted_file": False}]

    result = fmt.format(info, diff, [], [], None, "2", "main", "standard", None, None)

    assert '"additions": 42' in result
    assert '"deletions": 7' in result


def test_json_formatter_multiple_commits():
    fmt = JsonFormatter()
    info = {"title": "T", "author": {"name": "J"}, "state": "o", "source_branch": "f", "target_branch": "m", "web_url": "u", "description": ""}
    commits = [
        {"short_id": "aaa11111", "title": "first", "author_name": "A"},
        {"short_id": "bbb22222", "title": "second", "author_name": "B"},
    ]

    result = fmt.format(info, [], commits, [], None, "3", "main", "standard", None, None)

    assert '"sha": "aaa11111"' in result
    assert '"sha": "bbb22222"' in result
