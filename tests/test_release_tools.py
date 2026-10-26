import io
import subprocess
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

import publish
from scripts import release_check


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "uv_executable", lambda: "uv")
    (tmp_path / "bruhanimate").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "bruhanimate"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    (tmp_path / "bruhanimate/__init__.py").write_text(
        '__version__ = "1.0.0"\n', encoding="utf-8"
    )
    return tmp_path


@pytest.mark.parametrize(
    "value",
    ["-1.0.0", "01.0.0", "1.0", "1.0.0rc1", "v1.0.0", "1.0.0\n", "1.0.0;echo bad"],
)
def test_version_input_must_be_canonical_and_cannot_inject_outputs(value):
    with pytest.raises(ValueError):
        release_check.parse_version(value)


def test_version_check_uses_toml_and_ast_without_importing(project):
    module = project / "bruhanimate/__init__.py"
    module.write_text('raise RuntimeError("must not import")\n__version__ = "1.0.0"\n')
    assert release_check.source_version(project) == "1.0.0"
    module.write_text('__version__ = "0.9.0"\n')
    with pytest.raises(ValueError, match="agree"):
        release_check.source_version(project)


def test_bump_changes_only_the_project_version_and_module(project):
    pyproject, module = project / "pyproject.toml", project / "bruhanimate/__init__.py"
    pyproject.write_text(pyproject.read_text() + '\n[tool.other]\nversion = "1.0.0"\n')
    assert publish.bump_version(pyproject, module) == ((1, 0, 0), (1, 0, 1))
    assert release_check.source_version(project) == "1.0.1"
    assert '[tool.other]\nversion = "1.0.0"' in pyproject.read_text()


@pytest.mark.parametrize("target", [(1, 0, 0), (0, 9, 9), (-1, 1, 1)])
def test_invalid_bumps_leave_both_files_unchanged(project, target):
    paths = [project / "pyproject.toml", project / "bruhanimate/__init__.py"]
    originals = [p.read_bytes() for p in paths]
    with pytest.raises(ValueError):
        publish.bump_version(*paths, target)
    assert [p.read_bytes() for p in paths] == originals


def test_second_file_failure_rolls_back_first_version_file(project, monkeypatch):
    write = Path.write_text

    def fail_module(path, *args, **kwargs):
        if path.name == "__init__.py":
            raise OSError("write failed")
        return write(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_module)
    with pytest.raises(OSError, match="write failed"):
        publish.bump_version(
            project / "pyproject.toml", project / "bruhanimate/__init__.py"
        )
    assert release_check.source_version(project) == "1.0.0"


def test_preview_makes_no_writes_checks_or_git_calls(project, monkeypatch):
    validate, command = Mock(), Mock()
    monkeypatch.setattr(publish, "validate", validate)
    monkeypatch.setattr(publish, "command", command)
    assert publish.main([], root=project) == 0
    assert release_check.source_version(project) == "1.0.0"
    validate.assert_not_called()
    command.assert_not_called()


def test_current_release_check_does_not_bump(project, monkeypatch):
    validate = Mock()
    monkeypatch.setattr(publish, "validate", validate)
    assert publish.main(["--check"], root=project) == 0
    validate.assert_called_once_with(project)
    assert release_check.source_version(project) == "1.0.0"


def test_write_runs_checks_but_never_git(project, monkeypatch):
    validate, command = Mock(), Mock()
    monkeypatch.setattr(publish, "validate", validate)
    monkeypatch.setattr(publish, "command", command)
    assert publish.main(["1.1.0", "--write"], root=project) == 0
    assert release_check.source_version(project) == "1.1.0"
    validate.assert_called_once_with(project)
    command.assert_called_once_with(["uv", "lock"], root=project)


@pytest.mark.parametrize(
    "args",
    [["--commit"], ["--push"], ["--pr"], ["1.1.0", "--check"], ["--write", "--check"]],
)
def test_remote_operations_and_check_mode_require_unambiguous_flags(project, args):
    with pytest.raises(SystemExit):
        publish.main(args, root=project)
    assert release_check.source_version(project) == "1.0.0"


@pytest.mark.parametrize(
    "branch, status", [("main", ""), ("master", ""), ("feature", " M unrelated.py")]
)
def test_git_preflight_refuses_main_and_unrelated_work_before_mutating(
    project, monkeypatch, branch, status
):
    monkeypatch.setattr(publish, "command", Mock(side_effect=[branch, status]))
    with pytest.raises(ValueError):
        publish.main(["--write", "--commit"], root=project)
    assert release_check.source_version(project) == "1.0.0"


def test_failed_checks_leave_local_version_reviewable_but_do_not_commit(
    project, monkeypatch
):
    monkeypatch.setattr(publish, "preflight_git", Mock(return_value="codex/release"))
    monkeypatch.setattr(
        publish, "validate", Mock(side_effect=RuntimeError("tests failed"))
    )
    command = Mock()
    monkeypatch.setattr(publish, "command", command)
    with pytest.raises(RuntimeError, match="tests failed"):
        publish.main(["--write", "--commit", "--push"], root=project)
    command.assert_called_once_with(["uv", "lock"], root=project)
    assert release_check.source_version(project) == "1.0.1"


def test_lock_failure_stops_validation_and_git_after_a_local_bump(project, monkeypatch):
    monkeypatch.setattr(publish, "preflight_git", Mock(return_value="codex/release"))
    command = Mock(side_effect=subprocess.CalledProcessError(1, ["uv", "lock"]))
    validate = Mock()
    monkeypatch.setattr(publish, "command", command)
    monkeypatch.setattr(publish, "validate", validate)
    with pytest.raises(subprocess.CalledProcessError):
        publish.main(["--write", "--commit", "--push"], root=project)
    command.assert_called_once_with(["uv", "lock"], root=project)
    validate.assert_not_called()
    assert release_check.source_version(project) == "1.0.1"


def test_stale_lock_check_failure_stops_release_checks_without_changing_source(
    project, monkeypatch
):
    command = Mock(side_effect=subprocess.CalledProcessError(1, ["uv", "sync"]))
    monkeypatch.setattr(publish, "command", command)
    with pytest.raises(subprocess.CalledProcessError):
        publish.main(["--check"], root=project)
    command.assert_called_once_with(
        ["uv", "sync", "--locked", "--group", "docs", "--extra", "export"], root=project
    )
    assert release_check.source_version(project) == "1.0.0"


def test_explicit_pr_flow_checks_first_and_preserves_multiline_body(
    project, monkeypatch
):
    (project / "build").mkdir()
    calls = []
    monkeypatch.setattr(publish, "preflight_git", Mock(return_value="codex/release"))
    monkeypatch.setattr(publish, "validate", lambda root: calls.append("validated"))

    def command(args, **kwargs):
        calls.append(args)
        if args[:3] == ["gh", "pr", "create"]:
            body = Path(args[args.index("--body-file") + 1]).read_text()
            assert "Prepare bruhanimate 1.1.0.\n\nLocal" in body
            assert "\\n" not in body
            return "https://github.com/example/repo/pull/1"
        return ""

    monkeypatch.setattr(publish, "command", command)
    assert (
        publish.main(["1.1.0", "--write", "--commit", "--push", "--pr"], root=project)
        == 0
    )
    assert calls[0] == ["uv", "lock"]
    assert calls[1] == "validated"
    assert calls[2] == [
        "git",
        "add",
        "--",
        "pyproject.toml",
        "bruhanimate/__init__.py",
        "uv.lock",
    ]
    assert calls[3][:2] == ["git", "commit"]
    assert calls[4][:2] == ["git", "push"]
    assert not any(
        isinstance(call, list) and call[:2] == ["git", "tag"] for call in calls
    )


def make_dist(tmp_path, *, metadata_version="1.0.0", extra=None, omit_type=False):
    metadata = f"Name: bruhanimate\nVersion: {metadata_version}\n"
    modules = release_check.REQUIRED - ({"py.typed"} if omit_type else set())
    with zipfile.ZipFile(
        tmp_path / "bruhanimate-1.0.0-py3-none-any.whl", "w"
    ) as archive:
        archive.writestr("bruhanimate-1.0.0.dist-info/METADATA", metadata)
        for name in modules:
            archive.writestr(f"bruhanimate/{name}", "")
        if extra:
            archive.writestr(extra, "")
    with tarfile.open(tmp_path / "bruhanimate-1.0.0.tar.gz", "w:gz") as archive:
        contents = {
            "PKG-INFO": metadata,
            **{f"bruhanimate/{name}": "" for name in modules},
        }
        for name, text in contents.items():
            data = text.encode()
            info = tarfile.TarInfo(f"bruhanimate-1.0.0/{name}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return tmp_path


def test_distribution_check_accepts_matching_archives_without_extracting(tmp_path):
    release_check.check_dist(make_dist(tmp_path), "1.0.0")
    assert len(list(tmp_path.iterdir())) == 2


@pytest.mark.parametrize(
    "options",
    [
        {"metadata_version": "0.9.0"},
        {"omit_type": True},
        {"extra": "bruhanimate/bruhrenderer/base_renderer.py"},
        {"extra": "bruhanimate/.env"},
        {"extra": ".codegraph/index.sqlite"},
    ],
)
def test_distribution_check_rejects_wrong_metadata_missing_types_and_private_files(
    tmp_path, options
):
    with pytest.raises(ValueError):
        release_check.check_dist(make_dist(tmp_path, **options), "1.0.0")


def test_distribution_check_refuses_stale_archives(tmp_path):
    make_dist(tmp_path)
    (tmp_path / "old.whl").touch()
    with pytest.raises(ValueError, match="exactly"):
        release_check.check_dist(tmp_path, "1.0.0")


def workflow(name):
    root = Path(__file__).resolve().parents[1]
    # BaseLoader keeps YAML 1.2's workflow 'on' key as a string.
    return yaml.load(
        (root / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader
    )


def test_release_requires_tag_and_all_gates_before_privileged_upload():
    release = workflow("release.yml")
    assert "branches" not in release["on"]["push"]
    assert release["on"]["push"]["tags"] == ["v*"]
    jobs = release["jobs"]
    assert set(jobs["publish"]["needs"]) == {"verify", "checks", "docs"}
    assert jobs["checks"]["with"]["ref"] == "${{ needs.verify.outputs.commit }}"
    assert jobs["publish"]["permissions"]["id-token"] == "write"
    assert jobs["publish"]["environment"]["name"] == "pypi"
    upload = next(
        step
        for step in jobs["publish"]["steps"]
        if step.get("uses", "").startswith("pypa/gh-action-pypi-publish@")
    )
    assert "password" not in upload["with"]
    assert upload["with"]["attestations"] == "true"
    assert not any(
        "run" in step or "checkout" in step.get("uses", "")
        for step in jobs["publish"]["steps"]
    )
    assert release["permissions"] == {"contents": "read"}


def test_docs_prs_can_only_build_and_review_pinned_actions():
    docs = workflow("documentation.yml")
    assert "pull_request" in docs["on"]
    assert "refs/heads/main" in docs["jobs"]["deploy"]["if"]
    assert "pull_request" in docs["jobs"]["deploy"]["if"]
    assert docs["permissions"] == {"contents": "read"}
    for name in ("test.yml", "documentation.yml", "release.yml"):
        for job in workflow(name)["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    assert len(step["uses"].split("@")[1]) == 40
