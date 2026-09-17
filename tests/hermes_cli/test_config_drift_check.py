import os, subprocess, sys

SNAPSHOT = "/home/vjpixel/hermes-agent/.claude/worktrees/continuo-fix-6/config/hermes-home/config.yaml"
CHECK = "/home/vjpixel/hermes-agent/.claude/worktrees/continuo-fix-6/scripts/check_config_drift.py"

def test_redacted_ignored():
    output = subprocess.run([sys.executable, CHECK], capture_output=True, text=True)
    assert "password_hash" not in (output.stdout + output.stderr)

def test_no_auth_read():
    with open(CHECK) as f:
        src = f.read()
    # Garantia: não há aberto de auth.json para conteúdo; só referência de existência
    assert "open(" not in src.split("auth_path")[1] if "auth_path" in src else True
    # Nunca passa auth_path para yaml.safe_load / open de conteúdo
    assert "yaml.safe_load" not in src.split("auth_path")[1] if "auth_path" in src else True

def test_script_exists():
    assert os.path.isfile(CHECK)
