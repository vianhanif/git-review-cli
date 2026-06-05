import os

EXCLUDED_FILES = {
    "package-lock.json", "yarn.lock", ".npmrc", "go.sum", "go.mod",
}

EXCLUDED_EXTENSIONS = (".sum", ".png", ".jpg", ".ico")

CONFIG_PATTERNS = (
    ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini", ".env",
    "docker-compose", "Dockerfile", "Makefile",
)


def is_excluded(filepath: str) -> bool:
    basename = os.path.basename(filepath)
    return basename in EXCLUDED_FILES or filepath.endswith(EXCLUDED_EXTENSIONS)


def analyze_patterns(diff_data: list[dict]) -> dict:
    large_changes = []
    config_changes = []
    test_changes = []
    other_changes = []

    for f in diff_data:
        filepath = f.get("new_path", f.get("old_path", "?"))
        additions = f["additions"] if f.get("additions") is not None else (
            f.get("diff", "").count("\n+") if f.get("diff") else 0
        )
        deletions = f["deletions"] if f.get("deletions") is not None else (
            f.get("diff", "").count("\n-") if f.get("diff") else 0
        )
        total = additions + deletions

        if is_excluded(filepath):
            continue

        entry = (filepath, additions, deletions)

        if "test" in filepath.lower() or "spec" in filepath.lower():
            test_changes.append(entry)
        elif any(
            filepath.endswith(p) or os.path.basename(filepath) == p.lstrip(".")
            for p in CONFIG_PATTERNS
        ):
            config_changes.append(entry)
        elif total > 200:
            large_changes.append(entry)
        else:
            other_changes.append(entry)

    return {
        "large_changes": large_changes,
        "config_changes": config_changes,
        "test_changes": test_changes,
        "other_changes": other_changes,
        "has_tests": len(test_changes) > 0,
    }
