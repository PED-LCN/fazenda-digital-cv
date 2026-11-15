# Inferência por recortes em vídeo de alta resolução

Use `--tile-size` e `--tile-overlap` quando os bovinos ocuparem poucos pixels no quadro completo. O detector processa recortes sobrepostos, converte as caixas para coordenadas do quadro original e aplica NMS global para remover duplicatas. A opção usa o mesmo modelo ONNX e fica desativada por padrão. `--max-width 0` é obrigatório para preservar a resolução antes dos recortes.

```bash
fazenda-cv \
  --source datasets/mootrack360/farm1_area1_thread1_partial.mp4 \
  --model models/yolox_tiny.onnx \
  --source-id mootrack360-farm1-area1-thread1 \
  --detection-only --max-width 0 \
  --tile-size 736 --tile-overlap 96 \
  --max-frames 20 \
  --run-report artifacts/mootrack360_tiled_first20.json \
  --annotated artifacts/mootrack360_tiled_first20.avi
```

## Ensaio local em 14/11/2026

Fonte: [MooTrack360 Farm1 Area1](https://zenodo.org/records/20287681), arquivo `1-hour-farm1-area1-sample-sequence.zip`, câmera `Thread-1_video_writer_thread__seg0_area1.mp4`. A amostra local foi extraída dos primeiros 120 MB descompactados do MP4 enquanto o ZIP de 11,5 GB ainda era baixado. O arquivo parcial local tem SHA-256 `1aef13f56a8b8572b813d8a4a3b4317638ec2ed73c045808529bddae42c19276` e permite ler os primeiros 20 quadros. Os pesos YOLOX Tiny locais têm SHA-256 `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7`. Os arquivos de vídeo e pesos permanecem fora do Git.

Com o **mesmo quadro original de 2944 × 2944** e os mesmos 20 quadros do arquivo, os relatórios operacionais foram:

| Modo | Quadros com bovino detectado | Caixas | Máximo por quadro | FPS de processamento |
| --- | ---: | ---: | ---: | ---: |
| Quadro inteiro, `--max-width 0` | 0/20 | 0 | 0 | 17,98 |
| Recortes de 736 px, sobreposição 96 px | 20/20 | 85 | 8 | 1,70 |

A inspeção visual do primeiro quadro anotado mostrou quatro caixas sobre bovinos visíveis, com outros bovinos sem caixa. Isso confirma que o modo de recortes melhora a cobertura operacional **nesta amostra**, mas não mede precisão ou revocação. O custo foi cerca de 10 vezes mais tempo por quadro nesta máquina. Não use esse resultado para declarar contagem de entrada/saída: o trecho não tem acesso calibrado, e o modo `--detection-only` emitiu zero passagens por desenho.

Para aceitação quantitativa, anote caixas independentes em quadros separados dos usados para escolher tamanho/sobreposição, compare `score_frame` nos dois modos e meça FPS no hardware candidato. Calibre acesso/área somente após identificar a câmera e a geometria correspondente. O ZIP amostral não corresponde ao `gt.txt` da sequência anotada de uma hora.

## Avaliação inicial com vídeo e rótulos correspondentes

Foi obtido o início de `1hour_annotated_sequence.mp4`, que corresponde ao `gt.txt` do pacote TrackEval. Nas imagens de 2944 × 2944, as caixas MOT foram escaladas por 2, após inspeção visual do quadro 1; confira essa escala em mais quadros antes da avaliação final. O trecho local de 20.664.320 bytes tem SHA-256 `48848158e718dab535f1cf7b278d22c9aeb545b8beffc8c4ff8c0e5a14053a9b`.

```bash
.venv/bin/python scripts/evaluate_mot_detector.py \
  datasets/mootrack360/annotated_snapshot.mp4 \
  datasets/mootrack360/mot/gt.txt \
  models/yolox_tiny.onnx \
  --first-frame 1 --last-frame 20 --coordinate-scale 2 \
  --tile-size 736 --tile-overlap 96
```

Com IoU 0,5, o modo de recortes obteve **11 TP, 0 FP, 49 FN** sobre 60 caixas rotuladas: precisão 1,0 e revocação 0,183. No mesmo trecho, o quadro inteiro teve 0 TP, 0 FP e 60 FN. O conjunto de 20 quadros é pequeno, sequencial e foi usado para escolher os recortes; por isso é diagnóstico de desenvolvimento, não conjunto de avaliação separado. A maioria dos bovinos rotulados continua sem detecção. O FPS no hardware candidato também permanece pendente.

Nos quadros 101–120, que não foram usados no ajuste inicial dos recortes, ambos os modos obtiveram **0 TP, 0 FP, 60 FN** com a mesma escala e IoU. A revocação do modo de recortes nesse trecho foi 0. Assim, os recortes ainda não resolvem a limitação do YOLOX Tiny nesta câmera. É preciso avaliar um detector apropriado ou ajuste de pesos no próximo sprint antes de prometer monitoramento confiável.

Uma análise adicional variou o tamanho do recorte. Com **512 px e sobreposição 64 px**, o detector obteve 20 TP, 0 FP e 40 FN nos quadros 1–20 e também nos quadros 101–120: revocação de 33,3% em cada trecho. O recorte de 416 px nos quadros 101–105 teve 0 TP, 9 FP e 15 FN. No vídeo amostral, 512 px produziu 88 caixas em 20 quadros a **0,74 FPS** nesta máquina. Essa configuração melhora a cobertura, mas ainda perde dois terços dos bovinos e é lenta demais para prometer monitoramento em tempo real. Os quadros 101–120 deixam de ser um conjunto intocado para qualquer ajuste posterior feito com base nessa comparação; uma futura avaliação final precisa reservar outra sessão.
