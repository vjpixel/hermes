import os, subprocess, sys

# #26 (21/09/2026): was hardcoded to one worktree's absolute path on one
# machine — same bug the script itself had (fixed alongside #18's ruff
# cleanup), just missed here. Never caught before because this whole job
# always got stuck queued (unrelated large-runner issue, #26) and never
# actually ran to completion in CI until now.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECK = os.path.join(REPO_ROOT, "scripts", "check_config_drift.py")

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
