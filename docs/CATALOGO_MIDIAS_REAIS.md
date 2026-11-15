# Catálogo inicial de mídias reais

O [manifesto CSV](MANIFESTO_MIDIAS_REAIS.csv) registra dois GIFs de bovinos em estábulo e um quadro derivado, obtidos em 14/11/2026 do [Cow Tracking by Classification](https://github.com/meiqing-wang/Cow-TrackingbyClassification). O repositório publica [licença Apache-2.0](https://github.com/meiqing-wang/Cow-TrackingbyClassification/blob/main/LICENSE). A licença e as condições de quaisquer arquivos obtidos separadamente no acervo ETH precisam de verificação própria.

Os arquivos ficam em `datasets/cow_tracking/`, ignorado pelo Git. Para reproduzir o quadro derivado do primeiro GIF, execute:

```bash
ffmpeg -y -loglevel error -i datasets/cow_tracking/source/Demos/DayClip1.gif \
  -frames:v 1 datasets/cow_tracking/DayClip1_frame.png
.venv/bin/python -c 'from fazenda_cv.media_manifest import load_manifest; print(len(load_manifest("docs/MANIFESTO_MIDIAS_REAIS.csv")))'
```

O split `evaluation` reserva um GIF noturno distinto do GIF diurno de ajuste. Ambos já exibem caixas e identidades previstas pelos autores; **nenhum dos dois deve ser usado para calcular acurácia independente** do nosso detector ou rastreador. O quadro derivado permanece no mesmo split do GIF de origem. A câmera é superior em estábulo livre; oclusões são parciais. FPS e duração foram lidos com `ffprobe`, e os SHA-256 correspondem aos arquivos locais baixados/derivados.

O clipe CattleBehaviours6 usado no ensaio operacional da PR #24 ainda não entra neste manifesto: o [registro do Zenodo](https://zenodo.org/records/23064957) não declara licença no campo de direitos. Ele permanece apenas local enquanto as condições de uso são esclarecidas.
