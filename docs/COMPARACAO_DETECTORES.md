# Comparação de detectores para monitoramento

O ensaio de desenvolvimento usa 90 quadros do `video1` do
[Cow Tracking/ETH](https://doi.org/10.3929/ethz-c-000796658), em três janelas
consecutivas de 30 quadros. As referências amarelas e as detecções verdes
aparecem no primeiro quadro de cada janela. Confira as imagens do início, meio
e fim para detectar desalinhamento antes de interpretar as métricas.

Os perfis, origens e hashes dos pesos constam em
[`configs/benchmark/cattle_detectors.json`](../configs/benchmark/cattle_detectors.json).
Os caminhos são relativos à configuração. O exemplo assume a worktree ao lado
de `cv-monitoring`, onde estão os dados e modelos locais.

## Preparação em Linux

Use Python 3.12 e um ambiente para o ensaio. A instalação do CLI continua
descrita no README. Para o benchmark com todos os detectores:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu \
  'torch==2.8.0' 'torchvision==0.23.0'
.venv/bin/python -m pip install 'transformers==4.57.6' 'ultralytics==8.3.230' \
  'numpy==2.3.5' 'opencv-python==4.11.0.86' 'onnxruntime>=1.20,<2' 'ruff>=0.9,<1' 'pytest>=8.3,<9'
```

- Use os pesos oficiais YOLOX Tiny/S do release da configuração.
- Para RT-DETR, salve `config.json`, `preprocessor_config.json` e
  `model.safetensors` da revisão fixada no diretório `rtdetr_r50vd`.
- Para YOLOv8n, use somente `yolov8n_best.pt` da pasta indicada pelos autores.
  O checkpoint é opcional, tem formato PyTorch e requer procedência confiável.
  A licença específica dos pesos dos autores não foi identificada. Os pesos e
  dados desta comparação permanecem locais.

## Desenvolvimento e teste reservado

```bash
PYTHONPATH=src YOLO_CONFIG_DIR=artifacts/ultralytics .venv/bin/python \
  scripts/compare_cattle_detectors.py \
  --data ../cv-monitoring/datasets/cow_tracking/extracted \
  --config configs/benchmark/cattle_detectors.json \
  --output artifacts/comparacao-01
```

`comparison.json` e `comparison.csv` guardam os resultados por perfil. O pico
de memória é o RSS do processo completo e inclui o runtime e o decoder. O
primeiro quadro aquece cada perfil antes da medição. Compare latência sob
carga semelhante, em particular se outra avaliação estiver rodando na máquina.

A permanência é calculada após a primeira aquisição do animal em cada janela.
Os totais por ID somam acertos e oportunidades das três janelas. O relatório
mostra animais nunca adquiridos via cobertura e revocação. A configuração
selecionada exige revocação e precisão de 60% e permanência de 70% global e
por ID mensurável. A presença de `frozen.json` permite rodar o teste reservado:

```bash
PYTHONPATH=src YOLO_CONFIG_DIR=artifacts/ultralytics .venv/bin/python \
  scripts/compare_cattle_detectors.py \
  --data ../cv-monitoring/datasets/cow_tracking/extracted \
  --frozen artifacts/comparacao-01/frozen.json \
  --archive ../cv-monitoring/datasets/cow_tracking/downloads/tracking.tar.gz \
  --output artifacts/comparacao-01-reservado
```

Para retomar, repita o comando com o mesmo ambiente e diretório. Revise
`reserved.json` e os relatórios por minuto e por ID nos bancos de cada vídeo.
O peso dos autores foi publicado com o mesmo estudo. Confirme a composição do
treino se precisar declarar independência além da divisão publicada.

## Se o desenvolvimento exigir ajuste fino

Obtenha o pacote `detection.tar.gz` no acervo ETH e confira seu checksum.
Audite as sessões do treino e validação antes de configurar o `data.yaml`
com classe única `cow`. Use os vídeos reservados somente na avaliação. Na GTX
1050 Ti, valide suporte CUDA e inicie com o checkpoint oficial YOLOv8n:

```bash
yolo detect train model=yolov8n.pt data=data.yaml imgsz=640 batch=1 amp=False \
  device=0 workers=0 seed=42 epochs=1 project=artifacts/treino name=smoke
yolo detect train model=yolov8n.pt data=data.yaml imgsz=640 batch=1 amp=False \
  device=0 workers=0 seed=42 epochs=20 patience=5 project=artifacts/treino name=ajuste
```

Execute a segunda linha se o teste de uma época couber na GPU. Registre o
checkpoint `best.pt`, SHA-256, licença, dados e argumentos e inclua-o em nova
configuração de desenvolvimento. Se o teste de GPU falhar, preserve a tabela
dos pré-treinados e registre a causa.

Com a etapa de detecção concluída, use polígonos e caixas revisados para
calcular MAE e viés de contagem por região. Para novos quadros, teste Grounding
DINO offline, com prompt `cow.`, medindo tempo total de revisão e quantidade
de caixas aceitas, corrigidas e descartadas. Episódios de alerta exigem
referências humanas próprias.
