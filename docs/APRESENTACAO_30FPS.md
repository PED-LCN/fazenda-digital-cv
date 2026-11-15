# Cópia de apresentação a 30 ou 60 FPS — #39

```bash
PYTHONPATH=src .venv/bin/python -m fazenda_cv.presentation_video \
  ../cv-monitoring/artifacts/mootrack360_60s_tiled.avi \
  ../cv-monitoring/artifacts/mootrack360_apresentacao_30fps.mp4 --fps 30 --width 960
```

O comando gera H.264/MP4 com interpolação de movimento pelo FFmpeg, preserva a duração e recusa sobrescrever arquivos. O rodapé identifica a apresentação interpolada. Requer FFmpeg com minterpolate, drawtext e libopenh264. `--fps 60` gera alternativa a 60 FPS. As dimensões são reduzidas para apresentação, mantendo proporção.

A interpolação cria quadros visuais entre os quadros analisados. Não cria observações de bovinos nem altera JSON, fila ou métricas. A fonte do ensaio de um minuto foi amostrada a 2 FPS: 30 FPS exportados não significam captura ou detecção a 30 FPS. Interpolação pode distorcer caixas, textos ou animais durante oclusões; use o vídeo original para avaliar precisão. Os limites medidos de inferência estão em DETECTOR_CPU.md.

Teste automatizado gera fonte sintética de dois segundos, exporta a 30 e 60 FPS, confere 60/120 quadros e preservação dos bytes originais, além da recusa de sobrescrita. Execute `PYTHONPATH=src .venv/bin/pytest -q tests/test_presentation_video.py`. Na apresentação real, confira duração, FPS e quadros com ffprobe e revise visualmente transições/rodapé.
