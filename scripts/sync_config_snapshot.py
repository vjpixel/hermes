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
# A regex de redação, quando presente, casa a linha "chave: valor" (indentação
# preservada) E, se o valor for um block scalar YAML (|, |-, |+, >, >-, >+),
# todas as linhas de continuação mais indentadas que seguem — senão um
# password_hash escrito como bloco vazaria as linhas de continuação verbatim.
_PASSWORD_HASH_RE = re.compile(
    r"^(([ \t]*)password_hash:[ \t]*)"          # chave (\1) + indent isolado (\2)
    r"(?:[|>][+-]?[ \t]*\n(?:\2[ \t]+\S.*\n?)*"  # block scalar: só linhas MAIS
    r"|.*\n?)",                                  # indentadas que a chave (\2+)
    re.MULTILINE,
)

# Rede de segurança (review #31): a redação acima é uma allowlist de 1 chave.
# Se QUALQUER OUTRA chave com esse nome aparecer no conteúdo já processado com
# um valor que não seja o placeholder, o sync recusa a escrever — nunca versiona
# um segredo novo silenciosamente só porque ninguém lembrou de adicionar a
# chave à lista acima. Não substitui o allowlist explícito (esse continua
# sendo redigido corretamente, formato conhecido); é só o catch-all pro que
# ainda não foi ensinado a este script.
_KEY_LINE_RE = re.compile(r"^[ \t]*([\w.\-]+)[ \t]*:[ \t]*(\S.*)$", re.MULTILINE)
_ALLOWED_SUSPECT_VALUES = {"__redacted__", "null", "none", "~", '""', "''"}
# Whole WORDS only (key split on . _ -), never a bare substring — "tokens"
# in "max_tokens" must not trip on "token", "aliases" must not trip on
# anything. A standalone word from this set is enough to flag; "api"/
# "private" alone are too generic (api_version, private_beta, ...) so they
# only count paired with "key" as adjacent words.
_SUSPECT_WORDS = {"password", "passwd", "secret", "token", "key"}


def _key_words(key):
    return [w for w in re.split(r"[._\-]+", key.lower()) if w]


def _looks_suspect(key):
    words = _key_words(key)
    if any(w in _SUSPECT_WORDS for w in words):
        return True
    return any(
        a in ("api", "private") and b == "key"
        for a, b in zip(words, words[1:])
    )


class UnredactedSecretError(RuntimeError):
    pass


def find_unhandled_secrets(content, already_redacted_keys):
    """Return [(key, value)] for suspect-looking keys the redaction step
    didn't already neutralize. `already_redacted_keys` are key name
    fragments (lowercased) this file's own redaction regexes are known to
    handle, so a live match on one of those isn't flagged twice."""
    findings = []
    for m in _KEY_LINE_RE.finditer(content):
        key, value = m.group(1), m.group(2).strip()
        if not _looks_suspect(key):
            continue
        key_lower = key.lower()
        if any(handled in key_lower for handled in already_redacted_keys):
            continue
        if value.lower() in _ALLOWED_SUSPECT_VALUES:
            continue
        findings.append((key, value))
    return findings

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
        content = redact_re.sub(lambda m: f"{m.group(1)}__REDACTED__\n", content)
    return content


def _write_atomic(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp-{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)


def main():
    check_only = "--check" in sys.argv
    changed = []
    missing_live = []

    # Key fragments the redaction regexes above already know how to handle —
    # find_unhandled_secrets skips matches on these so the safety net doesn't
    # flag the very thing it's meant to let through once properly redacted.
    handled_key_fragments = {"password_hash"}

    for live_path, snap_path, redact_re in FILES:
        if not os.path.isfile(live_path):
            missing_live.append(live_path)
            continue

        new_content = build_snapshot_content(live_path, redact_re)

        leaks = find_unhandled_secrets(new_content, handled_key_fragments)
        if leaks:
            keys = ", ".join(k for k, _ in leaks)
            raise UnredactedSecretError(
                f"{live_path}: found key(s) that look like secrets and aren't "
                f"in the redaction allowlist: {keys}. Add them to "
                f"sync_config_snapshot.py before syncing — refusing to write "
                f"{snap_path}."
            )

        old_content = None
        if os.path.isfile(snap_path):
            with open(snap_path, "r", encoding="utf-8") as f:
                old_content = f.read()

        if new_content == old_content:
            continue

        changed.append(snap_path)
        if not check_only:
            _write_atomic(snap_path, new_content)

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
