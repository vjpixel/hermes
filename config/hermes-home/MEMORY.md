User's Linux machine has 32 GiB RAM, NVIDIA GeForce GTX 1060 Mobile with 6 GiB VRAM, and an Intel i7-7700HQ CPU.
§
User uses Tailscale and Termius for remote SSH access to the Linux machine.
§
Helios = Linux always-on (Hermes/CC local). Neo = Windows de Pixel (sessões logadas; label `windows`→develop no diaria-studio). Convenção: fix/feature pedido pelo Pixel → commitado no fork ao fim do trabalho. Remotes Hermes (24/08): origin=vjpixel/hermes (o updater SEGUE o fork), upstream=NousResearch (fetch manual), ossfork=vjpixel/hermes-agent (PRs públicos); branch backup/pre-update-local-main.
§
Pixel calls the always-on Linux machine “Helios”; when he says to execute something on Helios, use the current local machine rather than attempting an SSH connection.
§
Regra do Pixel (23/08): ler `gh issue view --comments` antes de perguntar; skill hermes-diaria-continuo: ciclo NÃO encerra prematuramente; review independente obrigatório pré-merge; fila (a) vazia → perguntas via `clarify` direto no chat (24/08).
§
Cron 'Diária Contínuo' (5d791ef6fc2c, every 30m): NÃO foi removido — estava pausado (13:31-20:20 de 28/08, por symlink quebrando os 2 watchdogs, #6646) e foi retomado (state=scheduled). Critério de fim de ciclo: ver skill canônica hermes/skills/hermes-diaria-continuo/SKILL.md (não parafrasear aqui — MEMORY.md:9 e esta linha já divergiram uma vez, #6643).
§
§
- Luna (gpt-5.6-luna) não funciona com conta ChatGPT OAuth — exige API key paga. Precisa `codex login --with-api-key`.
§
- Contas OpenAI OAuth no auth.json (3): vjpixel (p0), diaria.editor (p1), memelab (p2, adicionada 30/08 via device code). Todas sem créditos (HTTP 429).
§
- /no_think removido dos prompts dos cron jobs 496cd687d3e0 e 86303d0ed84b.
§
- daily-consolidated-review.sh corrigido para adicionar espaço após vírgula no marcador RESUMO-DAILY-REVIEW.
§
Pixel uses `claude-rc` launcher (NOT `hermes-claude-session`) for CC sessions on Helios. Canonical pair: `opus-diaria-rc` (Opus+high+RC) + `sonnet-diaria-medium` (Sonnet+medium+RC), both in ~/diaria-studio. Non-RC presets not used. Helios power outage ~Aug 30 22:30 killed gateway+tmux — recreate sessions after any gateway restart.