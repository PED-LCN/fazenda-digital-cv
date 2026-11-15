# Entrega de eventos por webhook — issue #8

A fila SQLite guarda eventos v2 antes de enviá-los. O publicador roda em processo separado da inferência: a indisponibilidade do receptor não bloqueia a análise. Use um único publicador por banco. A entrega é pelo menos uma vez: se houver queda depois do POST e antes da confirmação local, o receptor pode receber novamente o mesmo evento e deve deduplicar por `event_id`. `Idempotency-Key` contém esse identificador.

```bash
export CV_WEBHOOK_URL=http://127.0.0.1:8080/events
# CV_WEBHOOK_TOKEN opcional; configure por ambiente, sem gravar no Git.
python -m fazenda_cv.webhook --database artifacts/outbox.sqlite \
  --import-jsonl artifacts/eventos-v2.jsonl --once
# Para continuar retentativas e recuperar eventos após reinício:
python -m fazenda_cv.webhook --database artifacts/outbox.sqlite
```

Respostas 2xx confirmam entrega. Falhas HTTP, timeout e rede retentam após 2, 4, 8 segundos até o limite de 300 segundos. Não há descarte automático; erros 4xx também permanecem pendentes para corrigir URL/autenticação. O payload e ID persistem entre tentativas. Importações repetidas não duplicam eventos; reutilizar ID com payload diferente é rejeitado. O log imprime somente o número de confirmações.

Protocolo automatizado: `PYTHONPATH=src .venv/bin/pytest -q tests/test_webhook.py`. Um receptor HTTP local responde 503 e depois 200; o teste recria a fila, confirma espera, reenvio com ID/payload iguais, autenticação e ausência de novo envio após confirmação. Teste adicional rejeita conflitos de payload e versão v1.

O contrato v2 permanece candidato na PR #26. A entrega está preparada para receptor controlado; configurar o sistema consumidor real exige confirmar rota, autenticação e contrato com esse projeto. Esta feature não declara integração homologada com o ERP. Bancos, tokens e eventos ficam fora do Git.
