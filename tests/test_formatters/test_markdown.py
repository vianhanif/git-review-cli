import allure
from git_review_cli.formatters.markdown import MarkdownFormatter


@allure.feature("Formatters")
@allure.story("Markdown Output")
@allure.severity(allure.severity_level.CRITICAL)
class TestMarkdownFormatter:
    @allure.title("Standard mode renders MR metadata, commits, and file table")
    @allure.description("Verifies that the default markdown output includes the MR header, author, branch info, commits section, and changed files table with line counts.")
    def test_markdown_basic(self):
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
        diff = [{"new_path": "src/login.py", "additions": 10, "deletions": 2, "new_file": False, "deleted_file": False, "renamed_file": False}]
        commits = [{"short_id": "def67890", "title": "fix: login bug", "author_name": "Jane Doe"}]

        result = fmt.format(info, diff, commits, [], None, "42", "main", "standard", None, None)

        with allure.step("MR header contains number and title"):
            assert "MR !42" in result
            assert "Fix login bug" in result
        with allure.step("Author is rendered"):
            assert "Jane Doe" in result
        with allure.step("File table includes path and change counts"):
            assert "src/login.py" in result
            assert "+10/-2" in result
        with allure.step("Commits section is present"):
            assert "Commits" in result

    @allure.title("Caveman mode omits commits and deep findings")
    @allure.description("Verifies that --caveman output excludes the commits section for a compact view.")
    def test_markdown_caveman_skips_commits(self):
        fmt = MarkdownFormatter()
        info = {"iid": 1, "title": "T", "author": {"name": "A"}, "state": "o", "source_branch": "f", "target_branch": "m", "created_at": "d", "updated_at": "d", "web_url": "u", "description": ""}
        commits = [{"short_id": "abc", "title": "commit", "author_name": "A"}]

        result = fmt.format(info, [], commits, [], None, "1", "main", "caveman", None, None)

        assert "Commits" not in result

    @allure.title("Deep mode includes categorized findings")
    @allure.description("Verifies that --deep output renders the Findings section with large changes, config changes, missing tests warning, and all-changes summary.")
    def test_markdown_deep_includes_findings(self):
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

        with allure.step("Findings header is rendered"):
            assert "Findings & Observations" in result
        with allure.step("Large changes category is shown"):
            assert "Large Changes" in result
        with allure.step("Missing tests warning when no test files present"):
            assert "Missing Tests" in result

    @allure.title("Empty diff shows fallback message")
    def test_markdown_empty_diff_shows_message(self):
        fmt = MarkdownFormatter()
        info = {"iid": 1, "title": "T", "author": {"name": "A"}, "state": "o", "source_branch": "f", "target_branch": "m", "created_at": "d", "updated_at": "d", "web_url": "u", "description": ""}

        result = fmt.format(info, [], [], [], None, "1", "main", "standard", None, None)

        assert "Could not fetch diff data" in result

    @allure.title("Description whitespace is stripped")
    @allure.description("Leading and trailing blank lines and whitespace around the MR description should be cleaned up.")
    def test_markdown_description_stripping(self):
        fmt = MarkdownFormatter()
        info = {"iid": 1, "title": "T", "author": {"name": "A"}, "state": "o", "source_branch": "f", "target_branch": "m", "created_at": "d", "updated_at": "d", "web_url": "u", "description": "\n\n  Clean description  \n\n"}

        result = fmt.format(info, [], [], [], None, "1", "main", "standard", None, None)

        assert "Clean description" in result
