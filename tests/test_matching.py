from claw_keeper.matching import is_excluded, is_managed_repo_path


def test_exclude_patterns_match_root_and_nested_directories():
    patterns = ("logs/", "secrets/", "*.sqlite", "id_ed25519")

    assert is_excluded("logs/openclaw.log", patterns)
    assert is_excluded("workspace/logs/openclaw.log", patterns)
    assert is_excluded("secrets/value", patterns)
    assert is_excluded("memory/main.sqlite", patterns)
    assert is_excluded("workspace/id_ed25519", patterns)
    assert not is_excluded("workspace/AGENTS.md", patterns)


def test_managed_paths_include_configured_and_generated_paths():
    includes = ("workspace/", "openclaw.json")

    assert is_managed_repo_path("workspace/AGENTS.md", includes)
    assert is_managed_repo_path("openclaw.json", includes)
    assert is_managed_repo_path("manifests/latest.json", includes)
    assert is_managed_repo_path("reports/scan.md", includes)
    assert is_managed_repo_path(".gitignore", includes)
    assert not is_managed_repo_path("README.md", includes)
