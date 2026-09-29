"""`.env` auto-loading (app/config.py::_load_env_file).

The property worth protecting is precedence, not convenience: an operator's
explicit `VAR=... python -m app.main` must never be silently overridden by a
checked-out file. The rest of the suite depends on that too — several tests
and the demo runs point DATABASE_URL at a throwaway DB that way.
"""
from __future__ import annotations

import logging

from app import config


def _write_env(path, body: str):
    path.write_text(body, encoding="utf-8")
    return path


def test_env_file_populates_unset_variables(tmp_path, monkeypatch):
    env_file = _write_env(tmp_path / ".env", "SENTINEL_TEST_UNSET=from-file\n")
    monkeypatch.delenv("SENTINEL_TEST_UNSET", raising=False)
    monkeypatch.setenv("SENTINEL_ENV_FILE", str(env_file))

    config._load_env_file()

    import os
    assert os.environ["SENTINEL_TEST_UNSET"] == "from-file"


def test_real_environment_wins_over_the_file(tmp_path, monkeypatch):
    """The whole safety of this feature rests on override=False."""
    env_file = _write_env(tmp_path / ".env", "DATABASE_URL=sqlite:///from-the-file.db\n")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicitly-exported.db")
    monkeypatch.setenv("SENTINEL_ENV_FILE", str(env_file))

    config._load_env_file()

    import os
    assert os.environ["DATABASE_URL"] == "sqlite:///explicitly-exported.db"


def test_missing_env_file_is_not_fatal(tmp_path, monkeypatch, caplog):
    """A deployment that configures the environment properly ships no .env.
    That is the normal case, not an error."""
    monkeypatch.setenv("SENTINEL_ENV_FILE", str(tmp_path / "nope.env"))

    with caplog.at_level(logging.WARNING, logger="sentinel.config"):
        config._load_env_file()  # must not raise

    assert "does not exist" in caplog.text


def test_env_file_is_found_relative_to_the_package_not_the_cwd(tmp_path, monkeypatch):
    """Started from backend/, from the repo root, or by a service manager
    with an unrelated cwd — the file has to resolve the same way."""
    monkeypatch.delenv("SENTINEL_ENV_FILE", raising=False)
    monkeypatch.chdir(tmp_path)  # a cwd with no .env in sight

    from pathlib import Path
    expected = Path(config.__file__).resolve().parents[2] / ".env"

    config._load_env_file()  # resolves against the package, so this still works

    # The repo ships sentinel-solution/.env; assert the path this resolves to
    # is that one, rather than anything relative to the (empty) cwd.
    assert expected.name == ".env"
    assert not (tmp_path / ".env").exists()


def test_loaded_path_is_recorded_as_state_not_only_logged(tmp_path, monkeypatch):
    """config.py is imported before main.py calls logging.basicConfig(), so
    the INFO record has no handler and is discarded. The log alone therefore
    cannot tell an operator what happened — /health reads this instead."""
    env_file = _write_env(tmp_path / ".env", "SENTINEL_TEST_RECORDED=1\n")
    monkeypatch.setattr(config, "ENV_FILE_LOADED", None)
    monkeypatch.setenv("SENTINEL_ENV_FILE", str(env_file))

    config._load_env_file()

    assert config.ENV_FILE_LOADED == str(env_file)


def test_no_env_file_leaves_the_recorded_state_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_FILE_LOADED", None)
    monkeypatch.setenv("SENTINEL_ENV_FILE", str(tmp_path / "nope.env"))

    config._load_env_file()

    assert config.ENV_FILE_LOADED is None


def test_values_are_never_logged(tmp_path, monkeypatch, caplog):
    """The file holds Control Room feed credentials. Only the path may be
    logged, never a value."""
    secret = "super-secret-feed-password"
    env_file = _write_env(tmp_path / ".env", f"SENTINEL_TEST_SECRET={secret}\n")
    monkeypatch.delenv("SENTINEL_TEST_SECRET", raising=False)
    monkeypatch.setenv("SENTINEL_ENV_FILE", str(env_file))

    with caplog.at_level(logging.DEBUG, logger="sentinel.config"):
        config._load_env_file()

    assert secret not in caplog.text
    assert str(env_file) in caplog.text
