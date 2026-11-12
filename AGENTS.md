# Guia para agentes neste repositório

## Antes de alterar código

- Confirme `git status`, branch, base remota e a issue que será atendida. Preserve arquivos locais do usuário.
- Leia `README.md`, `docs/VALIDACAO.md` e, para gravações reais, `docs/PREPARACAO_GRAVACOES_REAIS.md` e `docs/BACKLOG_GRAVACOES_REAIS.md` quando existirem na branch.
- Mantenha uma responsabilidade por issue e por PR. Use nomes claros de domínio (`source`, `detector`, `tracker`, `passage`, `monitoring`) e interfaces pequenas; evite colocar regras de negócio dentro do CLI.

## Branches e PRs

- Crie uma branch `feat/<numero>-<assunto>` por issue. Se ela depender de uma feature ainda não incorporada, crie a branch a partir da branch dependida e abra a PR com essa branch como base. Confirme a base antes de publicar.
- As PRs de gravações reais abertas em 12/11/2026 formam estas cadeias: `main → #1 → #2 → #16`, `main → #1 → #3 → #4 → #6` e `main → #5 → #7`. Consulte o GitHub antes de trabalhar, pois merges podem mudar as bases.
- Cada PR deve trazer resumo, issue vinculada, comandos e resultados dos testes, protocolo de validação com gravação real e pendências. Use rascunho enquanto depender de mídia, pesos ou contrato externo não validados. Atualize a base das PRs filhas depois de cada merge.
- Não encerre uma issue apenas porque existe código ou testes sintéticos; confira todos os seus critérios de aceite.

## Testes e dados reais

- Para código novo, inclua testes unitários de comportamento e casos de erro no módulo correspondente. Execute `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .` e `.venv/bin/pytest -q` antes de commit/PR.
- Testes com Godot ou vídeos sintéticos verificam integração, não precisão no curral. Documente métricas em gravações reais separadas dos dados de ajuste antes de afirmar desempenho de campo ou a meta de 95%.
- Mídias, modelos, eventos locais e credenciais ficam fora do Git. Registre origem, licença, condições de uso e SHA-256 de mídia e pesos. Fotos não validam passagem, trajetória ou imobilidade.
- Preserve a saída de passagem v1 do CLI. O contrato v2 para integração precisa de revisão do projeto consumidor antes de ativar webhook. `track_id` vale apenas na fonte e sessão, não identifica permanentemente um bovino.
