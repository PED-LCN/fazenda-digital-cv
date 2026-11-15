# Totais por acesso e sessão — #18

`PassageTotals.record()` recebe eventos de passagem v2 e `rows()` retorna entradas e saídas por `source_id`, `session_id` e `access_id`. O mesmo event_id é contado uma vez; reuso com conteúdo diferente é erro. Reprocessar o mesmo conjunto gera os mesmos totais. Não se somam repetições do mesmo ID. Sessões de replay diferentes são consultas independentes, não uma população física acumulada.

```bash
PYTHONPATH=src .venv/bin/python -m fazenda_cv.passage_totals artifacts/eventos-v2.jsonl
```

O CLI lê JSONL, ignora eventos de outros tipos e imprime a lista JSON. Zero passagens produz `[]`; ausência de linha não significa ocupação zero. A consulta não identifica bovinos nem estima saldo inicial. A fila SQLite da #8 mantém payloads v2 e pode ser usada pelo consumidor; o stdout legado do CV permanece v1 e não deve ser enviado diretamente a esta consulta.

Teste: `PYTHONPATH=src .venv/bin/pytest -q tests/test_passage_totals.py`. Cobre os dois acessos, sessões e fontes independentes, reenvio, conflito, direção inválida e conjunto sem passagens. A exatidão dos totais deriva dos eventos fornecidos; a medição de passagens reais continua no aceite da #17.

Para consultar diretamente os eventos persistidos pelo CV, incluindo confirmados e pendentes, sem exportar arquivos:

```bash
PYTHONPATH=src .venv/bin/python -m fazenda_cv.passage_totals --outbox artifacts/outbox.sqlite3
```

A conexão é somente leitura e não modifica o estado de entrega. Um teste integra inserção na fila real e consulta dos totais.
