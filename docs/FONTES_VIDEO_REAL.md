# Fontes candidatas para demonstração com vídeo real

| Fonte | Uso nesta entrega | Limite relevante |
| --- | --- | --- |
| [CattleBehaviours6](https://zenodo.org/records/23064957) | Clipe curto e sem sobreposição de predições para mostrar leitura de vídeo e detecção | 1.905 clipes rotulados em seis comportamentos; não há rótulos de passagem nem caixas por quadro declarados no registro. O [catálogo da Universidade de Bristol](https://data.bristol.ac.uk/data/dataset/b5c8h75pug4m235p3po6ogitc) informa a licença Non-Commercial Government Licence; confira seus termos antes de redistribuir. |
| [Cow Tracking by Classification](https://github.com/meiqing-wang/Cow-TrackingbyClassification) | Referência de arquitetura e, no [acervo ETH](https://www.research-collection.ethz.ch/entities/researchdata/fe7242ce-d8bc-4e56-92a6-8c7e312432b0), avaliação futura de rastreamento | Os GIFs locais já mostram predições; o acervo separado oferece seis vídeos de teste rotulados em `tracking.tar.gz` (7,88 GB). O modelo usa YOLOv8 e classificação de indivíduos, sem encaixe direto no adaptador YOLOX ONNX. A licença do acervo ETH permite uso não comercial. |
| [MooTrack360](https://zenodo.org/records/20287681) | Avaliação futura de detecção/rastreamento e candidato para acessos virtuais | O pacote de plantas tem regiões `gate` e `milking_station` e configurações de câmeras. Há vídeo anotado de 1 hora e sequências amostrais; os arquivos de vídeo são grandes (11,5 GB e 18,9 GB), com imagem olho de peixe. O repositório dos autores informa CC BY-NC-SA 4.0. |

## Escopo da demonstração

Um vídeo real processado com pesos YOLOX ONNX, saída anotada e `--run-report` comprova funcionamento técnico da leitura, inferência e gravação. O relatório operacional registra detecções e FPS, mas **não** comprova precisão de contagem, classificação de comportamento ou eventos de evasão. Para medir essas funcionalidades serão necessários vídeos com passagens/ocorrências anotadas e câmera semelhante à do projeto.

Arquivos de mídia e pesos ficam em `datasets/`, `videos/` e `models/`, ignorados pelo Git. Registre hashes e URLs originais antes de reproduzir os resultados. Não publique cópia dos vídeos sem licença confirmada. O ajuste fino do detector fica para o próximo sprint após medir os erros no material real.

## Potencial para as issues de acesso e rastreamento

O pacote `Floorplans_and_extrinsic_calibration.zip` do MooTrack360 foi baixado e inspecionado localmente. Em `Farm2_Area_1`, a planta lista duas regiões `gate` e duas `milking_station`; em `Farm2_Area_2-3`, quatro portões e uma estação; em `Farm2_Area_4`, um portão e uma estação. O vídeo de 1 hora e os pacotes amostrais ainda precisam ser examinados para descobrir quais desses acessos aparecem em cada câmera e se há cruzamentos observáveis. As coordenadas publicadas estão na planta em metros; não devem ser copiadas diretamente para as linhas normalizadas da imagem.

Os seis vídeos rotulados do Cow Tracking são candidatos diretos à avaliação de trocas de identidade e oclusões da issue #6. O artigo descreve bovinos saindo e voltando ao campo de visão; isso é diferente de uma entrada ou saída física de curral/ordenha. Para as issues #2 e #16, é preciso inspecionar a gravação e rotular acesso, instante e sentido antes de usar qualquer cruzamento. A resposta anterior de que as fontes não tinham vídeos relevantes foi ampla demais: a limitação correta é que **os vídeos completos com rótulos de acesso ainda não foram baixados nem examinados**.

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

Resultado local: 50 quadros processados; 47 quadros com ao menos uma detecção, 56 caixas ao todo, máximo de 2 caixas num quadro, 0 eventos de passagem e cerca de 35,9 FPS de processamento nesta máquina. O vídeo anotado contém 50 quadros; uma inspeção visual do primeiro quadro confirmou uma caixa verde sobre o bovino. Os números são observações da execução, não precisão nem revocação. O clipe mostra alimentação e não contém acesso de curral/ordenha; portanto não valida contagem de entradas e saídas. O Zenodo não declara licença no campo de direitos; o catálogo da Universidade de Bristol informa a Non-Commercial Government Licence. O clipe permanece local e fora do Git.

## Inventário dos comportamentos disponíveis

O ZIP local foi inspecionado em 15/11/2026: contém 1.905 clipes distribuídos em `feeding` (398), `drinking` (243), `standing-self-grooming` (352), `standing-ruminating` (283), `standing-ruminating-part2` (161), `lying-self-grooming` (175) e `lying-ruminating` (293). A pasta `part2` usa a mesma classe de ruminação em pé, totalizando as seis classes descritas pelos autores. `labels.json`, `train.txt`, `val.txt` e `test.txt` permitem selecionar exemplos sem misturar treino e teste. A classe é do clipe inteiro; não há início/fim rotulado de imobilidade, queda ou passagem. Trechos desses clipes podem testar leitura e detecção em cenas variadas, mas não aferir os alertas temporais.

Quatro clipes do `test.txt` foram lidos integralmente com o mesmo YOLOX Tiny e limiar padrão 0,35, sem redimensionamento adicional. Cada clipe tem 50 quadros. A tabela mostra apenas quadros com alguma detecção; não há caixas de referência para medir acerto.

| Clipe | Comportamento rotulado | Quadros com detecção | Caixas detectadas |
| --- | --- | ---: | ---: |
| `00062.mp4` | Alimentação | 47/50 | 56 |
| `00233.mp4` | Bebida | 0/50 | 0 |
| `00093.mp4` | Ruminação deitado | 5/50 | 5 |
| `00132.mp4` | Ruminação em pé | 0/50 | 0 |

Essas diferenças mostram que uma cena de alimentação isolada não representa os outros comportamentos. Os relatórios JSON locais estão em `artifacts/cattlebehaviours6_*_repeat.json`. Antes de qualquer alerta que dependa de detecção contínua, é necessário comparar caixas anotadas em cada tipo de cena e qualificar pesos mais adequados.
