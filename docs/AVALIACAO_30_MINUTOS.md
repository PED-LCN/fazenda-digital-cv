# Avaliação contínua de 30 minutos — #44

O ensaio de dois segundos da #42 é somente diagnóstico. Não satisfaz o aceite de duração e movimentação desta entrega. A avaliação longa usa vídeos completos com GT por quadro do [Cow Tracking](https://github.com/meiqing-wang/Cow-TrackingbyClassification), distribuídos pelo [ETH Zurich](https://doi.org/10.3929/ethz-c-000796658).

## Material e sequência

O pacote oficial `tracking.tar.gz` tem 8.263.032.538 bytes e MD5 `7aab872f1117aa46317b370b7f53b91d`, consultados na API do acervo. Condição de uso: In Copyright — Non-Commercial Use Permitted, conforme metadados DataCite do DOI. Os arquivos ficam fora do Git.

Os autores descrevem video3 como diurno de 30min01s, 11 animais e 12 reaparições, e video4 como noturno de 30min, 11 animais e 10 reaparições. Esses números são metadados dos autores, não resultados do nosso CV. A atividade será conferida com GT, deslocamento, reaparições e imagens de revisão ao longo de toda a gravação. Não se selecionam apenas intervalos fáceis.

Video1, de cinco minutos, é exclusivamente desenvolvimento: cinco quadros no início, meio e fim calibram Tiny/S, quadro completo/recortes 1280/960 e limiares 0,35/0,20/0,10/0,05. O perfil congelado antes de qualquer avaliação longa foi YOLOX-S 640, recortes 1280, sobreposição 128, confiança 0,20 e quatro threads. No desenvolvimento: revocação 62,9%, precisão 78,6%, permanência 96,7%; esses valores não aprovam a avaliação de 30 minutos. Os candidatos iniciais sem recortes falharam; seus relatórios foram preservados com sufixo `initial_fullframe`.

## Execução

```bash
PYTHONPATH=src .venv/bin/python -u scripts/run_long_cattle_job.py \
  --archive ../cv-monitoring/datasets/cow_tracking/downloads/tracking.tar.gz \
  --data ../cv-monitoring/datasets/cow_tracking/extracted \
  --models ../cv-monitoring/models \
  --output ../cv-monitoring/artifacts/long44
```

Ajuste os caminhos ao checkout com os dados. O download usa blocos HTTP de 16 MiB, verifica `Content-Range`, retoma bytes já recebidos e respeita espera de retentativa. O MD5 do pacote completo é obrigatório antes do relatório final do trabalho. A extração lê o arquivo em crescimento, só aceita arquivos regulares sob `tracking_new/video1`, `video3` e `video4`, e usa `.part` até concluir cada vídeo. Assim, a análise pode começar antes de baixar todo o pacote; resultados ficam provisórios até a verificação de integridade.

O worker processa **todos os quadros decodificados**, sem looping, interpolação ou amostragem para inflar a duração. A coluna de classe dos rótulos YOLO significa ID do bovino, não classe COCO. Ausência de arquivo de rótulo falha; arquivo vazio é um quadro negativo válido. A sequência de rótulos deve começar em zero e não pode ter lacunas.

No primeiro vídeo real, o cabeçalho anunciou 4.518 quadros, enquanto o vídeo decodificado e os rótulos têm 4.501. Por isso a execução usa cobertura de rótulos, verifica o EOF real, guarda timestamps crescentes de cada quadro e calcula a duração analisada a partir desses timestamps. Não usa somente `frame_count/FPS` para declarar 30 minutos. Ao retomar, reconstrói a posição por decodificação sequencial, evitando deslocamento de quadros em arquivos VFR.

## Persistência e resultados

Cada vídeo tem SQLite próprio com metadados imutáveis e observações por quadro. Commits a cada 100 quadros permitem retomar sem duplicar contagens; quadros do lote não confirmado podem ser inferidos novamente. Alterações no vídeo, rótulos, detector, parâmetros ou código invalidam o checkpoint. A permanência global atravessa fronteiras de minutos; não reinicia artificialmente a aquisição a cada minuto.

A pasta `artifacts/long44` contém:

- `job.json`: estado global, sem declarar aprovação antes de concluir os dois vídeos e conferir o pacote.
- `download.json` e `download.log`: origem, integridade e progresso/retentativas.
- `development_video1.json` e `frozen_configuration.json`: seleção anterior ao teste longo.
- `video3.sqlite3` / `video4.sqlite3`: rótulos, caixas atuais, correspondências e timestamp de cada quadro.
- `video3.progress.json` / `video4.progress.json`: quantidade confirmada e tempo de vídeo analisado.
- `video3.summary.json` / `video4.summary.json`: TP/FP/FN, revocação, precisão, permanência global, por minuto e por ID, reaparições, movimento em pixels e maior sequência de perdas.
- `video3_scene_review/` / `video4_scene_review/`: quadros originais de 0, 5, 10, 15, 20, 25 e 29min59s para revisão visual de atividade.

```bash
PYTHONPATH=src .venv/bin/python scripts/long_evaluation_status.py \
  ../cv-monitoring/artifacts/long44 \
  --archive ../cv-monitoring/datasets/cow_tracking/downloads/tracking.tar.gz
```

O comando de status é somente leitura. O trabalho pode levar horas de download e inferência nesta CPU. Duração de 30 minutos de gravação não significa processar em 30 minutos reais nem conseguir 30 FPS ao vivo.

## Critérios e testes

As definições de pareamento IoU 0,5 e permanência seguem BATERIA_DETECCAO.md. Nenhuma caixa é carregada para pontuar um quadro sem inferência atual. `global_targets_met` exige todo o vídeo, pelo menos 1.800 s reais analisados, revocação >=60% e permanência global >=70%. `target_met` exige adicionalmente permanência >=70% de **cada** ID adquirido e mensurável. Uma aquisição só no último quadro não é prova de permanência. A precisão e os bovinos nunca adquiridos continuam explícitos.

A atividade dos vídeos e os casos de oclusão precisam de revisão humana dos artefatos. O estado final automatizado é `completed_requires_scene_review`, e não homologação do CV em campo. Se a métrica falhar, não se ajusta usando o mesmo vídeo para depois chamá-lo de teste reservado.

Testes unitários verificam parser de IDs, duplicatas, rejeição de vídeo curto/rótulo ausente, retomada equivalente à execução contínua, ausência de duplicação, estado temporal atravessando minutos, cabeçalho com contagem exagerada, leitura do arquivo em crescimento e download por intervalo com checksum. Execute `PYTHONPATH=src .venv/bin/pytest -q tests/test_long_evaluation.py`. Esses fixtures sintéticos validam o executor; não contam como os testes reais de 30 minutos.
