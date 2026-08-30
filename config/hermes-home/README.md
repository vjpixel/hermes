# hermes-home — snapshot versionado do `~/.hermes`

Fecha a lacuna da issue #6: a config de runtime do Hermes vivia só na máquina,
com um rastro de `config.yaml.bak-*` ao lado servindo de histórico informal.
Aqui ela tem `git log`, diff e review.

## O que tem aqui

| arquivo | origem na máquina | papel |
|---|---|---|
| `config.yaml` | `~/.hermes/config.yaml` | config global — **sanitizado**, ver abaixo |
| `profiles/coding-config.yaml` | `~/.hermes/profiles/coding/config.yaml` | perfil isolado do `hermes-diaria-continuo` |
| `profiles/coding-profile.yaml` | `~/.hermes/profiles/coding/profile.yaml` | descrição do perfil |
| `MEMORY.md` | `~/.hermes/memories/MEMORY.md` | memória durável do agente |

## Sanitização

`dashboard.basic_auth.password_hash` é substituído por `__REDACTED__`. O valor
real (scrypt) fica só no arquivo da máquina. **Ao restaurar a partir daqui,
reponha o hash antes de subir o dashboard** — senão a auth do dashboard quebra.

Nenhuma API key vive nestes arquivos: as credenciais do Hermes ficam em
`~/.hermes/auth.json`, que NÃO é versionado e não deve ser.

## Snapshot, não symlink

Este diretório é uma cópia, não a fonte de runtime. O Hermes continua lendo
`~/.hermes/`. Sincronizar é manual e consciente — copiar de volta por cima da
config viva sem ler o diff é o jeito de perder uma edição feita na máquina.

Um symlink resolveria a divergência, mas versionaria o `password_hash` junto —
foi por isso que ficou snapshot. Automatizar o sync (com a redação aplicada nos
dois sentidos) é trabalho em aberto na #6.

## O que NÃO está aqui, de propósito

- `auth.json` (credenciais)
- `sessions/`, `state.db`, `kanban.db` (estado de runtime)
- `skills/` (vive em repo próprio; a `hermes-diaria-continuo` é symlink pro
  `diaria-studio`, ver #6446 de lá)

## Aviso sobre o bloco `smart_model_routing`

O `config.yaml` aqui **inclui** o bloco `smart_model_routing:` — perfis
`coding`/`general`/`simple`, `default_profile`, `fallback_chains`. Ele **não
roteia nada** desde `424e9f36b0` ("refactor: remove smart_model_routing
feature #12732", abr/2026). Hoje só alimenta o allowlist do picker do
`/model` (`model_catalog.picker_scope: routing`, #6673).

Editar aquele bloco esperando mudar roteamento é um erro que já aconteceu duas
vezes (#6620, #6645, ambas no-ops). O que roteia de verdade: `model.default` +
`fallback_providers` (global, sem perfis) e `gateway.profile_routes` por perfil.

Destino do bloco: #9.
