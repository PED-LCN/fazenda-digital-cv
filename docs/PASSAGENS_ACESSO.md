# Passagens por acesso — #17

Use `--accesses-config config.json --access-id curral` (ou `ordenha`) para selecionar fonte e linha independentes do arquivo da issue #16. `--line` é rejeitado com essa configuração. Acrescente `--outbox artifacts/outbox.sqlite3` para persistir eventos v2 com acesso, sessão e posição temporal, mantendo JSON v1 no stdout. Cada execução processa uma fonte; execute uma por câmera. A orientação da linha define entrada/saída.

O contador existente aplica debounce por trilha. track_id não identifica o animal. Configuração e emissão podem ser testadas localmente; o aceite de erro de contagem permanece pendente de passagens reais rotuladas e oclusões. Não use a sequência de monitoramento como prova de acesso físico.
