# Fontes candidatas para demonstração com vídeo real

| Fonte | Uso nesta entrega | Limite relevante |
| --- | --- | --- |
| [CattleBehaviours6](https://zenodo.org/records/23064957) | Clipe curto e sem sobreposição de predições para mostrar leitura de vídeo e detecção | 1.905 clipes rotulados por comportamento; não há rótulos de passagem nem caixas por quadro declarados no registro. A licença não aparece no campo `Rights` da página; conferir os metadados/arquivo antes de redistribuir. |
| [Cow Tracking by Classification](https://github.com/meiqing-wang/Cow-TrackingbyClassification) | Referência de arquitetura e GIFs para inspeção qualitativa | Código Apache-2.0, mas os GIFs já mostram caixas e identidades previstas. O modelo publicado usa YOLOv8 e classificação de indivíduos; não encaixa diretamente no adaptador YOLOX ONNX nem demonstra entradas/saídas. Os pesos estão em Google Drive. |
| [MooTrack360](https://zenodo.org/records/20287681) | Avaliação futura de detecção/rastreamento sob oclusão e iluminação variável | Vídeo anotado de 1 hora e modelos publicados, mas o pacote total tem 199 GB, imagens olho de peixe e fluxo de referência orientado a CUDA. O repositório dos autores informa CC BY-NC-SA 4.0. |

## Escopo da demonstração

Um vídeo real processado com pesos YOLOX ONNX, saída anotada e `--run-report` comprova funcionamento técnico da leitura, inferência e gravação. O relatório operacional registra detecções e FPS, mas **não** comprova precisão de contagem, classificação de comportamento ou eventos de evasão. Para medir essas funcionalidades serão necessários vídeos com passagens/ocorrências anotadas e câmera semelhante à do projeto.

Arquivos de mídia e pesos ficam em `datasets/`, `videos/` e `models/`, ignorados pelo Git. Registre hashes e URLs originais antes de reproduzir os resultados. Não publique cópia dos vídeos sem licença confirmada. O ajuste fino do detector fica para o próximo sprint após medir os erros no material real.

## Ensaio executado em 14/11/2026

Foi usado `CattleBehaviours6/feeding/00062.mp4`, listado no `test.txt` do arquivo original, com 50 quadros a 5 FPS (10 segundos, 176 × 336). O arquivo ZIP baixado tem SHA-256 `4b6cf7eafbd3590931215f33a8baf3f0fa5c25236ed501d09d58383e6c1e8659`; o clipe extraído tem SHA-256 `8e8b1fbda3856f2c72955361f2fcb5dd7206af1ecbfb6f05e233f0e106917eed`. Os pesos [YOLOX Tiny oficiais](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx) têm SHA-256 `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7`. A licença específica dos pesos ainda precisa de confirmação antes de distribuição.

```bash
unzip -j datasets/cattle_behaviours6/CattleBehaviours6.zip \
  CattleBehaviours6/feeding/00062.mp4 -d datasets/cattle_behaviours6/samples
.venv/bin/fazenda-cv \
  --source datasets/cattle_behaviours6/samples/00062.mp4 \
  --model models/yolox_tiny.onnx \
  --source-id cattlebehaviours6-feeding-00062 \
  --detection-only \
  --annotated artifacts/cattlebehaviours6_00062_detection.avi \
  --run-report artifacts/cattlebehaviours6_00062_detection.json
```

Resultado local: 50 quadros processados; 47 quadros com ao menos uma detecção, 56 caixas ao todo, máximo de 2 caixas num quadro, 0 eventos de passagem e cerca de 35,9 FPS de processamento nesta máquina. O vídeo anotado contém 50 quadros; uma inspeção visual do primeiro quadro confirmou uma caixa verde sobre o bovino. Os números são observações da execução, não precisão nem revocação. O clipe mostra alimentação e não contém acesso de curral/ordenha; portanto não valida contagem de entradas e saídas. O registro do Zenodo não declara uma licença no campo de direitos, então o clipe permanece local e fora do Git.
