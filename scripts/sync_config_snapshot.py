#!/usr/bin/env python3
"""Sincroniza o snapshot versionado (config/hermes-home/) a partir do config
vivo (~/.hermes/), aplicando a redação necessária.
Referência: vjpixel/hermes #6

Direção ÚNICA: vivo -> snapshot. Nunca escreve de volta em ~/.hermes/ — ver
config/hermes-home/README.md ("Sincronizar é manual e consciente... symlink
resolveria a divergência, mas versionaria o password_hash junto").

Cópia de texto puro (não round-trip via yaml.safe_load/dump): preserva
comentários e formatação do arquivo vivo, que é onde o histórico de decisões
realmente é documentado inline.

Uso: python3 scripts/sync_config_snapshot.py [--check]
  --check   não escreve nada; sai 1 se o snapshot ficaria diferente do que
            geraria a partir do vivo (útil pra CI/cron), 0 se já está igual.
"""
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_DIR = os.path.join(REPO_ROOT, "config", "hermes-home")

# (fonte no vivo, destino no snapshot, regex de redação ou None)
# A regex de redação, quando presente, casa a linha inteira "chave: valor"
# (indentação preservada) e substitui o valor por __REDACTED__.
_PASSWORD_HASH_RE = re.compile(r"^(\s*password_hash:\s*).*$", re.MULTILINE)

FILES = [
    (
        os.path.expanduser("~/.hermes/config.yaml"),
        os.path.join(SNAPSHOT_DIR, "config.yaml"),
        _PASSWORD_HASH_RE,
    ),
    (
        os.path.expanduser("~/.hermes/profiles/coding/config.yaml"),
        os.path.join(SNAPSHOT_DIR, "profiles", "coding-config.yaml"),
        None,
    ),
    (
        os.path.expanduser("~/.hermes/profiles/coding/profile.yaml"),
        os.path.join(SNAPSHOT_DIR, "profiles", "coding-profile.yaml"),
        None,
    ),
    (
        os.path.expanduser("~/.hermes/memories/MEMORY.md"),
        os.path.join(SNAPSHOT_DIR, "MEMORY.md"),
        None,
    ),
]


def build_snapshot_content(live_path, redact_re):
    with open(live_path, "r", encoding="utf-8") as f:
        content = f.read()
    if redact_re is not None:
        content = redact_re.sub(r"\1__REDACTED__", content)
    return content


def main():
    check_only = "--check" in sys.argv
    changed = []
    missing_live = []

    for live_path, snap_path, redact_re in FILES:
        if not os.path.isfile(live_path):
            missing_live.append(live_path)
            continue

        new_content = build_snapshot_content(live_path, redact_re)

        old_content = None
        if os.path.isfile(snap_path):
            with open(snap_path, "r", encoding="utf-8") as f:
                old_content = f.read()

        if new_content == old_content:
            continue

        changed.append(snap_path)
        if not check_only:
            os.makedirs(os.path.dirname(snap_path), exist_ok=True)
            with open(snap_path, "w", encoding="utf-8") as f:
                f.write(new_content)

    if missing_live:
        for p in missing_live:
            print(f"AVISO: fonte viva não encontrada, pulando: {p}", file=sys.stderr)

    if changed:
        verb = "ficaria(m) diferente(s)" if check_only else "atualizado(s)"
        print(f"{len(changed)} arquivo(s) {verb}:")
        for p in changed:
            print(f"  {os.path.relpath(p, REPO_ROOT)}")
        sys.exit(1 if check_only else 0)
    else:
        print("Snapshot já está sincronizado com o config vivo.")
        sys.exit(0)


if __name__ == "__main__":
    main()
