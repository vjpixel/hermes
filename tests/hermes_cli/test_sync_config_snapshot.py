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
    live.write_text("key: value\n")
    snap = tmp_path / "snap.yaml"
    # snapshot starts out-of-date on purpose

    monkeypatch.setattr(mod, "FILES", [(str(live), str(snap), None)])
    monkeypatch.setattr(mod.sys, "argv", ["sync_config_snapshot.py", "--check"])

    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 1

    assert not snap.exists(), "--check must never write the snapshot file"


def test_sync_writes_and_is_idempotent(tmp_path, monkeypatch):
    mod = _load_module()

    live = tmp_path / "live.yaml"
    live.write_text("key: value\n")
    snap = tmp_path / "snap.yaml"

    monkeypatch.setattr(mod, "FILES", [(str(live), str(snap), None)])
    monkeypatch.setattr(mod.sys, "argv", ["sync_config_snapshot.py"])

    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 0
    assert snap.read_text() == "key: value\n"

    # second run: nothing changed, should report no-op (exit 0) and not
    # touch the file's mtime-relevant content again
    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 0
