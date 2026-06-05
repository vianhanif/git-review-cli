import pytest
from git_review_cli.analyzers.patterns import is_excluded, analyze_patterns


class TestIsExcluded:
    def test_lockfiles_are_excluded(self):
        assert is_excluded("package-lock.json") is True
        assert is_excluded("sub/dir/yarn.lock") is True
        assert is_excluded(".npmrc") is True
        assert is_excluded("go.sum") is True
        assert is_excluded("go.mod") is True

    def test_binary_extensions_are_excluded(self):
        assert is_excluded("icon.png") is True
        assert is_excluded("images/photo.jpg") is True
        assert is_excluded("favicon.ico") is True
        assert is_excluded("checksum.sum") is True

    def test_source_files_are_not_excluded(self):
        assert is_excluded("src/main.go") is False
        assert is_excluded("app.py") is False
        assert is_excluded("components/Button.tsx") is False
        assert is_excluded("config.yaml") is False


class TestAnalyzePatterns:
    def test_empty_diff(self):
        result = analyze_patterns([])
        assert result["large_changes"] == []
        assert result["config_changes"] == []
        assert result["test_changes"] == []
        assert result["other_changes"] == []
        assert result["has_tests"] is False

    def test_detects_test_files(self):
        data = [
            {"new_path": "src/api_test.go", "additions": 20, "deletions": 5},
        ]
        result = analyze_patterns(data)
        assert len(result["test_changes"]) == 1
        assert result["test_changes"][0][0] == "src/api_test.go"
        assert result["has_tests"] is True

    def test_detects_config_files(self):
        data = [
            {"new_path": "docker-compose.yml", "additions": 10, "deletions": 0},
            {"new_path": "Dockerfile", "additions": 5, "deletions": 0},
            {"new_path": ".gitlab-ci.yml", "additions": 30, "deletions": 0},
        ]
        result = analyze_patterns(data)
        assert len(result["config_changes"]) == 3

    def test_detects_large_changes(self):
        data = [
            {"new_path": "src/big_refactor.py", "additions": 150, "deletions": 80},
        ]
        result = analyze_patterns(data)
        assert len(result["large_changes"]) == 1  # 150+80=230 > 200

    def test_small_changes_are_other(self):
        data = [
            {"new_path": "src/helper.py", "additions": 10, "deletions": 2},
        ]
        result = analyze_patterns(data)
        assert len(result["other_changes"]) == 1
        assert result["other_changes"][0][0] == "src/helper.py"

    def test_excluded_files_are_skipped(self):
        data = [
            {"new_path": "go.sum", "additions": 50, "deletions": 20},
            {"new_path": "go.mod", "additions": 5, "deletions": 3},
        ]
        result = analyze_patterns(data)
        assert result["large_changes"] == []
        assert result["config_changes"] == []
        assert result["other_changes"] == []

    def test_falls_back_to_diff_counting(self):
        data = [
            {"new_path": "src/app.py", "diff": "\n+line1\n+line2\n-line3"},
        ]
        result = analyze_patterns(data)
        assert result["other_changes"][0][1] == 2
        assert result["other_changes"][0][2] == 1

    def test_additions_none_prefers_api_value(self):
        data = [
            {"new_path": "src/app.py", "additions": 42, "deletions": 7},
        ]
        result = analyze_patterns(data)
        assert result["other_changes"][0][1] == 42
        assert result["other_changes"][0][2] == 7
