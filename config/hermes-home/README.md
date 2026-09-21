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
foi por isso que ficou snapshot.

## Sync: vivo -> snapshot (`scripts/sync_config_snapshot.py`)

`python3 scripts/sync_config_snapshot.py` copia os 4 arquivos da tabela acima
do vivo pro snapshot, aplicando a redação do `password_hash` no caminho. Cópia
de texto puro — preserva comentários e formatação do arquivo vivo (que é onde
o histórico de decisões é documentado inline), nunca um round-trip via
`yaml.safe_load`/`dump` que reformataria e perderia isso.

Direção ÚNICA: vivo -> snapshot. **Nunca** escreve de volta em `~/.hermes/` —
symlink continua descartado pelo motivo acima, e sync automático nos DOIS
sentidos reintroduziria o mesmo risco ("copiar de volta por cima da config
viva sem ler o diff é o jeito de perder uma edição feita na máquina").

`--check` não escreve nada, só sai 1 se o snapshot ficaria diferente — para
rodar em CI/cron como verificação, análogo ao `check_config_drift.py` mas
comparando arquivo a arquivo em vez de valor a valor (cobre `MEMORY.md` e os
2 arquivos de perfil, que `check_config_drift.py` não olha).

Rodar depois de qualquer sessão que tenha editado `~/.hermes/config.yaml`,
`~/.hermes/profiles/coding/*.yaml` ou `~/.hermes/memories/MEMORY.md` — nenhum
gatilho automático existe ainda (próximo passo natural seria um job de cron
do próprio Hermes rodando isso periodicamente, não feito aqui de propósito:
criar infra de cron nova é decisão operacional separada, mesma cautela do
#8).

## O que NÃO está aqui, de propósito

- `auth.json` (credenciais)
- `sessions/`, `state.db`, `kanban.db` (estado de runtime)
- `skills/` (vive em repo próprio; a `hermes-diaria-continuo` é symlink pro
  `diaria-studio`, ver #6446 de lá)

## O bloco `smart_model_routing` foi REMOVIDO (#9, 31/08/2026)

Não existe mais, nem aqui nem no `~/.hermes/config.yaml` da máquina. Ele não
roteava nada desde `424e9f36b0` ("refactor: remove smart_model_routing feature
#12732", abr/2026), e editá-lo esperando mudar roteamento foi um erro cometido
duas vezes (#6620, #6645, ambas no-ops).

A única coisa que ainda o consumia era o allowlist do picker do `/model`
(`model_catalog.picker_scope: routing`, #6673). Isso acabou no PR #12: o
allowlist passou a derivar da CADEIA VIVA (`fallback_providers` + o legado
`fallback_model`, via `get_fallback_chain`) + o primary de `model:` +
`picker_extras`. Medido antes de remover: o allowlist é **idêntico** (5 pares)
com e sem o bloco.

O que roteia de verdade: `model.default` + `fallback_providers` (global, sem
perfis) e `gateway.profile_routes` por perfil.

Se um `config.yaml` antigo ainda trouxer o bloco, ele é lido apenas como
fallback de último recurso, quando não há cadeia nenhuma declarada.
