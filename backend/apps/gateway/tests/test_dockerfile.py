"""The Dockerfile lists each workspace member's pyproject.toml by hand (for layer caching).
Forgetting one breaks the image build, so check the list against the workspace."""

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]


def test_every_workspace_member_is_copied_before_dependency_install() -> None:
    dockerfile = (BACKEND / "Dockerfile").read_text()
    members = sorted(
        p.parent.relative_to(BACKEND).as_posix()
        for group in ("apps", "libs", "modules")
        for p in (BACKEND / group).glob("*/pyproject.toml")
    )
    assert members, "no workspace members found"
    missing = [
        m for m in members if f"COPY {m}/pyproject.toml {m}/pyproject.toml" not in dockerfile
    ]
    assert not missing, f"add to the Dockerfile's dependency layer: {missing}"
