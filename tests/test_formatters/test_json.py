import allure
from git_review_cli.formatters.json import JsonFormatter


@allure.feature("Formatters")
@allure.story("JSON Output")
@allure.severity(allure.severity_level.NORMAL)
class TestJsonFormatter:
    @allure.title("Basic JSON output includes MR metadata, commits, and file diffs")
    @allure.description("Verifies that the JSON formatter produces valid output with all expected top-level keys and correct value types.")
    def test_json_formatter_basic(self):
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

        result = fmt.format(info, diff, commits, [], None, "1", "main", "standard", None, None)

        with allure.step("MR title is serialized"):
            assert '"title": "Test MR"' in result
        with allure.step("MR number is serialized"):
            assert '"number": "1"' in result
        with allure.step("File path is serialized"):
            assert '"path": "src/app.py"' in result
        with allure.step("Line counts from diff fallback"):
            assert '"additions": 1' in result
            assert '"deletions": 1' in result
        with allure.step("New file flag is serialized"):
            assert '"new_file": true' in result

    @allure.title("JSON output uses API additions/deletions when available")
    @allure.description("When the API provides explicit additions/deletions values, those are used in the JSON output rather than diff string counting.")
    def test_json_formatter_uses_api_additions(self):
        fmt = JsonFormatter()
        info = {"title": "T", "author": {"name": "J"}, "state": "o", "source_branch": "f", "target_branch": "m", "web_url": "u", "description": ""}
        diff = [{"new_path": "src/app.py", "additions": 42, "deletions": 7, "new_file": False, "deleted_file": False}]

        result = fmt.format(info, diff, [], [], None, "2", "main", "standard", None, None)

        assert '"additions": 42' in result
        assert '"deletions": 7' in result

    @allure.title("JSON output includes multiple commits")
    @allure.description("All commits from the MR are serialized in the commits array with SHA, title, and author.")
    def test_json_formatter_multiple_commits(self):
        fmt = JsonFormatter()
        info = {"title": "T", "author": {"name": "J"}, "state": "o", "source_branch": "f", "target_branch": "m", "web_url": "u", "description": ""}
        commits = [
            {"short_id": "aaa11111", "title": "first", "author_name": "A"},
            {"short_id": "bbb22222", "title": "second", "author_name": "B"},
        ]

        result = fmt.format(info, [], commits, [], None, "3", "main", "standard", None, None)

        assert '"sha": "aaa11111"' in result
        assert '"sha": "bbb22222"' in result
