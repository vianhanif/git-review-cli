import allure
import pytest
from git_review_cli.analyzers.patterns import is_excluded, analyze_patterns


@allure.feature("Analyzers")
@allure.story("File Exclusion")
@allure.severity(allure.severity_level.CRITICAL)
class TestIsExcluded:
    @allure.title("Lockfiles are excluded from analysis")
    @allure.description("Verifies that common lockfiles (npm, yarn, Go) are flagged as noise and excluded from diff analysis.")
    def test_lockfiles_are_excluded(self):
        with allure.step("Check package-lock.json"):
            assert is_excluded("package-lock.json") is True
        with allure.step("Check yarn.lock in subdirectory"):
            assert is_excluded("sub/dir/yarn.lock") is True
        with allure.step("Check .npmrc"):
            assert is_excluded(".npmrc") is True
        with allure.step("Check go.sum"):
            assert is_excluded("go.sum") is True
        with allure.step("Check go.mod"):
            assert is_excluded("go.mod") is True

    @allure.title("Binary and checksum extensions are excluded")
    @allure.description("Verifies that image and checksum files (.png, .jpg, .ico, .sum) are flagged as excluded.")
    def test_binary_extensions_are_excluded(self):
        assert is_excluded("icon.png") is True
        assert is_excluded("images/photo.jpg") is True
        assert is_excluded("favicon.ico") is True
        assert is_excluded("checksum.sum") is True

    @allure.title("Source code and config files are not excluded")
    @allure.description("Verifies that legitimate source files (.go, .py, .tsx, .yaml) pass through without exclusion.")
    def test_source_files_are_not_excluded(self):
        assert is_excluded("src/main.go") is False
        assert is_excluded("app.py") is False
        assert is_excluded("components/Button.tsx") is False
        assert is_excluded("config.yaml") is False


@allure.feature("Analyzers")
@allure.story("Pattern Analysis")
@allure.severity(allure.severity_level.CRITICAL)
class TestAnalyzePatterns:
    @allure.title("Empty diff produces empty results")
    @allure.description("An empty diff list should return all empty categories and has_tests=False.")
    def test_empty_diff(self):
        result = analyze_patterns([])
        with allure.step("All categories are empty"):
            assert result["large_changes"] == []
            assert result["config_changes"] == []
            assert result["test_changes"] == []
            assert result["other_changes"] == []
        with allure.step("No test files detected"):
            assert result["has_tests"] is False

    @allure.title("Detects test files by naming convention")
    @allure.description("Files containing 'test' or 'spec' in their path are classified as test changes.")
    def test_detects_test_files(self):
        data = [{"new_path": "src/api_test.go", "additions": 20, "deletions": 5}]
        result = analyze_patterns(data)
        assert len(result["test_changes"]) == 1
        assert result["test_changes"][0][0] == "src/api_test.go"
        assert result["has_tests"] is True

    @allure.title("Detects configuration and infra files")
    @allure.description("Dockerfiles, CI configs, and other infra files are classified as config changes.")
    def test_detects_config_files(self):
        data = [
            {"new_path": "docker-compose.yml", "additions": 10, "deletions": 0},
            {"new_path": "Dockerfile", "additions": 5, "deletions": 0},
            {"new_path": ".gitlab-ci.yml", "additions": 30, "deletions": 0},
        ]
        result = analyze_patterns(data)
        with allure.step("All three config files detected"):
            assert len(result["config_changes"]) == 3

    @allure.title("Detects large changes (>200 lines total)")
    @allure.description("Files with combined additions+deletions exceeding 200 lines are flagged as large changes.")
    def test_detects_large_changes(self):
        data = [{"new_path": "src/big_refactor.py", "additions": 150, "deletions": 80}]
        result = analyze_patterns(data)
        assert len(result["large_changes"]) == 1

    @allure.title("Small files are categorized as 'other'")
    def test_small_changes_are_other(self):
        data = [{"new_path": "src/helper.py", "additions": 10, "deletions": 2}]
        result = analyze_patterns(data)
        assert len(result["other_changes"]) == 1
        assert result["other_changes"][0][0] == "src/helper.py"

    @allure.title("Excluded files are completely skipped")
    @allure.description("Lockfiles with large diffs should be entirely removed from analysis categories.")
    def test_excluded_files_are_skipped(self):
        data = [
            {"new_path": "go.sum", "additions": 50, "deletions": 20},
            {"new_path": "go.mod", "additions": 5, "deletions": 3},
        ]
        result = analyze_patterns(data)
        assert result["large_changes"] == []
        assert result["config_changes"] == []
        assert result["other_changes"] == []

    @allure.title("Falls back to raw diff counting when API values missing")
    @allure.description("When additions/deletions keys are absent from the API response, line counts are derived from the diff string.")
    def test_falls_back_to_diff_counting(self):
        data = [{"new_path": "src/app.py", "diff": "\n+line1\n+line2\n-line3"}]
        result = analyze_patterns(data)
        with allure.step("Counts 2 addition lines"):
            assert result["other_changes"][0][1] == 2
        with allure.step("Counts 1 deletion line"):
            assert result["other_changes"][0][2] == 1

    @allure.title("Prefers API additions/deletions over diff counting")
    @allure.description("When the API provides additions and deletions values, those are used directly without falling back to diff parsing.")
    def test_additions_none_prefers_api_value(self):
        data = [{"new_path": "src/app.py", "additions": 42, "deletions": 7}]
        result = analyze_patterns(data)
        assert result["other_changes"][0][1] == 42
        assert result["other_changes"][0][2] == 7
