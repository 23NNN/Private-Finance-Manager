"""Guards against drift between pyproject.toml and README/docs."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
DOC_FILES = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]


def test_readme_badge_matches_project_version() -> None:
    """The README version badge must equal ``project.version``."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"badge/Version-([0-9.]+)-", readme)
    assert match, "README has no version badge"
    assert match.group(1) == PYPROJECT["project"]["version"]


def test_documented_extras_exist() -> None:
    """Every ``.[extra]`` mentioned in README/docs must be defined in pyproject.toml."""
    defined = set(PYPROJECT["project"]["optional-dependencies"])
    for path in DOC_FILES:
        for group in re.findall(r"-e \.\[([^\]]+)\]", path.read_text(encoding="utf-8")):
            for extra in group.split(","):
                assert extra.strip() in defined, f"{path.name}: unknown extra '{extra.strip()}'"
