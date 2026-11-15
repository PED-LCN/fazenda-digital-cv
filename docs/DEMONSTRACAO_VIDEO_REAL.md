# Demonstração com vídeo real e eventos — issue #33

Esta branch combina #7, #8, #28 e a correção de FPS #30 para apresentação local. A PR tem #8 como base; os merges de dependências ainda abertas não representam incorporação na main.

## Selecionar cenas sem copiar o vídeo

```bash
PYTHONPATH=src .venv/bin/python -m fazenda_cv \
  --source ../cv-monitoring/datasets/mootrack360/farm1_area1_thread1_partial.mp4 \
  --model ../cv-monitoring/models/yolox_tiny.onnx \
  --source-id mootrack360-farm1-area1 \
  --detection-only --max-width 0 \
  --tile-size 512 --tile-overlap 64 --confidence-threshold 0.2 \
  --start-seconds 60 --duration-seconds 10 --frame-step 20 \
  --annotated ../cv-monitoring/artifacts/demo_segment_60_70.avi \
  --run-report ../cv-monitoring/artifacts/demo_segment_60_70.json
```

A fonte percorre o arquivo em sequência para preservar a posição original, decodificando para imagem somente os quadros selecionados. O FPS de saída é FPS original dividido por `frame-step`; os deslocamentos dos eventos continuam referindo-se ao arquivo original. Seleção é exclusiva de arquivos com FPS válido. A duração resulta da quantidade de quadros selecionados e pode arredondar em até um intervalo de amostragem. Um arquivo parcial pode terminar antes do trecho pedido; confira o número de quadros no relatório. Intervalos grandes podem perder cruzamentos e quebrar trajetórias; para passagens use todos os quadros.

O ensaio acima foi executado no vídeo real: 5 quadros, 47 caixas, 5 quadros com detecção, zero passagens e 0,29 FPS nesta máquina; ffprobe confirmou saída de 10 s a 0,5 FPS. São evidências operacionais, sem caixas de referência nessa sequência. Uma gravação mais fluida de 60 segundos, a 2 FPS, permanece em `../cv-monitoring/artifacts/mootrack360_60s_tiled.avi`. Os pesos ainda falham em diversas cenas; consulte INFERENCIA_RECORTES.md.

## Demonstrar os eventos

No comando de passagem existente, acrescente `--access-id curral --outbox artifacts/outbox.sqlite3 --events artifacts/passagens-v1.jsonl`. A linha deve ser configurada sobre um acesso observado. O stdout e JSONL mantêm v1; cada passagem observada também entra na fila como v2, preservando o mesmo ID, sessão e posição temporal. A rede não participa do processamento dos quadros. Para transmitir a fila, use outro terminal:

```bash
PYTHONPATH=src .venv/bin/python -m fazenda_cv.webhook \
  --database artifacts/outbox.sqlite3 --url http://127.0.0.1:8080/events
```

O receptor deve aceitar POST JSON e deduplicar `event_id`. URL/token de ambiente e retentativas estão em WEBHOOK.md. O teste `test_video_file_to_cv_events_and_annotated_video` verifica passagem sintética até JSON v1, fila v2 e saída anotada. `test_webhook.py` verifica HTTP real com receptor local, erro 503, reinício e sucesso. Isso valida a integração técnica; a rota do outro sistema ainda precisa ser homologada. A sequência real de monitoramento não tem acesso calibrado e gerou zero passagens; não há evento inventado para apresentá-la como passagem real.

Validação: `PYTHONPATH=src .venv/bin/pytest -q`, Ruff, formatação e `git diff --check`. Os testes de seleção verificam offsets 1000, 1200, 1400, 1600 e 1800 ms e FPS de saída 5 para um arquivo 10 FPS amostrado a cada dois quadros.
