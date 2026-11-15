# Ocupação por região — #10

Cada quadro processado pode gerar um evento v2 `occupancy` por região configurada, com count, source_id, session_id e video_offset_ms. Uma caixa pertence à região quando seu centro está dentro ou sobre a borda. Regiões sobrepostas contam a mesma caixa independentemente. Não há identificação individual nem inferência de população real: falsos positivos e omissões do detector afetam a estimativa. Uma região sem detecção emite count=0; isso não prova curral vazio. `authorized_area` serve de limite visual; as contagens usam `regions`.

```bash
PYTHONPATH=src .venv/bin/python -m fazenda_cv \
  --source ../cv-monitoring/datasets/mootrack360/annotated_prefix.mp4 \
  --model ../cv-monitoring/models/yolox_tiny.onnx \
  --source-id mootrack --areas-config /tmp/mootrack-areas.json \
  --detection-only --max-width 0 --tile-size 512 --tile-overlap 64 \
  --max-frames 5 --occupancy-events artifacts/ocupacao-v2.jsonl \
  --outbox artifacts/ocupacao.sqlite3
```

O JSON de áreas segue a #9; exemplo de região de teste (não é calibração de curral):

```json
{"sources":[{"source_id":"mootrack","authorized_area":[[0,0],[1,0],[1,1],[0,1]],"regions":[{"region_id":"quadro","polygon":[[0,0],[1,0],[1,1],[0,1]]}]}]}
```

A prévia/vídeo anotado mostra os polígonos. O arquivo occupancy-events é v2; o stdout legado permanece reservado às passagens v1. O outbox pode ser entregue pelo worker da #8. O CLI emite uma medição por quadro e região, sem limitação de frequência adicional: use frame-step para ensaios amostrados. Vídeos amostrados não validam trajetórias ou passagens.

Testes cobrem borda, interior/exterior, regiões sobrepostas, zero detecções e referência temporal. Para aceite final, compare as contagens com caixas reais de avaliação por região e publique erro por quadro. A baixa revocação já observada nos pesos impede declarar precisão operacional; a PR permanece em rascunho.

## Ensaio real executado

Em MooTrack360 `annotated_prefix.mp4`, quadros 1–5, recortes 512/64 e limiar 0,35, a região de teste cobriu o quadro inteiro. Foram emitidos cinco eventos count=1, com offsets 0, 67, 133, 200 e 267 ms, e cinco registros na fila. O GT MOT correspondente contém três caixas por quadro: erro absoluto 2 em cada quadro, média 2 e subcontagem total 10 nas cinco observações. A referência temporal e a comparação foram verificadas por frame, conforme protocolo de escala da avaliação de detector. Esse trecho já foi usado no ajuste; o ensaio comprova emissão real e evidencia subcontagem, sem ser avaliação independente. Artefatos locais: `../cv-monitoring/artifacts/ocupacao-v2.jsonl` e `ocupacao.sqlite3`. Não equivale a cinco bovinos distintos: são cinco observações temporais.
