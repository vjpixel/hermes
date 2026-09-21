import importlib.util
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "sync_config_snapshot.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("sync_config_snapshot", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_exists():
    assert os.path.isfile(SCRIPT)


def test_password_hash_redacted(tmp_path):
    mod = _load_module()
    live = tmp_path / "config.yaml"
    live.write_text(
        "dashboard:\n"
        "  basic_auth:\n"
        "    password_hash: scrypt$16384$8$1$realvalue==$moredata==\n"
        "    other_key: keep_me\n"
    )
    content = mod.build_snapshot_content(str(live), mod._PASSWORD_HASH_RE)
    assert "scrypt" not in content
    assert "realvalue" not in content
    assert "password_hash: __REDACTED__" in content
    assert "other_key: keep_me" in content


def test_no_redaction_when_regex_is_none(tmp_path):
    mod = _load_module()
    live = tmp_path / "profile.yaml"
    live.write_text("name: coding\nsome_secret_looking_field: not_actually_redacted\n")
    content = mod.build_snapshot_content(str(live), None)
    assert content == live.read_text()


def test_check_mode_never_writes(tmp_path, monkeypatch):
    mod = _load_module()

    live = tmp_path / "live.yaml"
    live.write_text("some_field: value\n")
    snap = tmp_path / "snap.yaml"
    # snapshot starts out-of-date on purpose

    monkeypatch.setattr(mod, "FILES", [(str(live), str(snap), None)])
    monkeypatch.setattr(mod.sys, "argv", ["sync_config_snapshot.py", "--check"])

    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 1

    assert not snap.exists(), "--check must never write the snapshot file"


def test_password_hash_block_scalar_redacted(tmp_path):
    """Review #31: the single-line regex used to leave block-scalar
    continuation lines (password_hash: |) verbatim in the snapshot."""
    mod = _load_module()
    live = tmp_path / "config.yaml"
    live.write_text(
        "dashboard:\n"
        "  basic_auth:\n"
        "    password_hash: |\n"
        "      scrypt$16384$8$1$secretsalt==\n"
        "      moresecretdata==\n"
        "    other_key: keep_me\n"
        "next_field: still_here\n"
    )
    content = mod.build_snapshot_content(str(live), mod._PASSWORD_HASH_RE)
    assert "scrypt" not in content
    assert "secretsalt" not in content
    assert "moresecretdata" not in content
    assert "password_hash: __REDACTED__" in content
    # continuation redaction must not swallow the next sibling key
    assert "other_key: keep_me" in content
    assert "next_field: still_here" in content


def test_safety_net_catches_unhandled_secret_key():
    mod = _load_module()
    content = "openrouter_api_key: sk-live-abc123\nother: fine\n"
    leaks = mod.find_unhandled_secrets(content, already_redacted_keys={"password_hash"})
    assert leaks == [("openrouter_api_key", "sk-live-abc123")]


def test_safety_net_does_not_flag_already_redacted_password_hash():
    mod = _load_module()
    content = "password_hash: __REDACTED__\n"
    leaks = mod.find_unhandled_secrets(content, already_redacted_keys={"password_hash"})
    assert leaks == []


def test_safety_net_ignores_whole_word_false_positives():
    """max_tokens must not trip on the substring 'token'; 'aliases' etc.
    must not trip on nothing in particular."""
    mod = _load_module()
    content = (
        "max_tokens: 16384\n"
        "aliases:\n"
        "  laguna: poolside/laguna-s-2.1\n"
        "api_version: v3\n"
        "private_beta: true\n"
    )
    leaks = mod.find_unhandled_secrets(content, already_redacted_keys=set())
    assert leaks == []


def test_safety_net_catches_api_key_compound_word():
    mod = _load_module()
    content = "api_key: sk-abc\n"
    leaks = mod.find_unhandled_secrets(content, already_redacted_keys=set())
    assert leaks == [("api_key", "sk-abc")]


def test_sync_raises_and_refuses_to_write_on_unhandled_secret(tmp_path, monkeypatch):
    mod = _load_module()

    live = tmp_path / "live.yaml"
    live.write_text("api_key: sk-live-real-value\n")
    snap = tmp_path / "snap.yaml"

    monkeypatch.setattr(mod, "FILES", [(str(live), str(snap), None)])
    monkeypatch.setattr(mod.sys, "argv", ["sync_config_snapshot.py"])

    import pytest

    with pytest.raises(mod.UnredactedSecretError):
        mod.main()

    assert not snap.exists()


def test_main_end_to_end_redacts_password_hash_and_does_not_raise(tmp_path, monkeypatch):
    """Review #31 finding 3: the redaction unit tests and the main()
    integration tests never overlapped before, so nothing proved the real
    regex + safety net actually cooperate when driven through main()."""
    mod = _load_module()

    live = tmp_path / "config.yaml"
    live.write_text(
        "dashboard:\n"
        "  basic_auth:\n"
        "    password_hash: scrypt$16384$8$1$realvalue==\n"
        "model:\n"
        "  default: some-model\n"
    )
    snap = tmp_path / "snap.yaml"

    monkeypatch.setattr(mod, "FILES", [(str(live), str(snap), mod._PASSWORD_HASH_RE)])
    monkeypatch.setattr(mod.sys, "argv", ["sync_config_snapshot.py"])

    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 0

    written = snap.read_text()
    assert "scrypt" not in written
    assert "password_hash: __REDACTED__" in written
    assert "default: some-model" in written


def test_sync_writes_and_is_idempotent(tmp_path, monkeypatch):
    mod = _load_module()

    live = tmp_path / "live.yaml"
    live.write_text("some_field: value\n")
    snap = tmp_path / "snap.yaml"

    monkeypatch.setattr(mod, "FILES", [(str(live), str(snap), None)])
    monkeypatch.setattr(mod.sys, "argv", ["sync_config_snapshot.py"])

    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 0
    assert snap.read_text() == "some_field: value\n"

    # second run: nothing changed, should report no-op (exit 0) and not
    # touch the file's mtime-relevant content again
    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 0
