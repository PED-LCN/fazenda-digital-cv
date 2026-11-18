# Anotação de monitoramento

Liste cada mídia no manifesto antes de rotular. `boxes` registra bovinos em quadros amostrados, com coordenadas `xyxy` normalizadas e região. Em fotos, use `frame_ms: 0`. `episodes` registra intervalos positivos e negativos de `crowding`, `immobility`, `boundary_exit` ou `outside_area` em vídeos; não use fotos para avaliar eventos temporais.

```json
{
  "boxes": [
    {"media_id": "clip_1", "frame_ms": 1000, "region_id": "curral", "xyxy": [0.1, 0.2, 0.4, 0.6]}
  ],
  "episodes": [
    {"media_id": "clip_1", "kind": "crowding", "region_id": "curral", "start_ms": 1000, "end_ms": 4000, "positive": true},
    {"media_id": "clip_1", "kind": "outside_area", "region_id": "curral", "start_ms": 5000, "end_ms": 7000, "positive": false}
  ]
}
```

Um trecho negativo deve representar uma situação em que o alerta seria plausível, mas incorreto, como animais próximos sem aglomeração. Guarde a regra de rotulagem e registre revisão de discordâncias entre anotadores. Separe ajuste e avaliação por vídeo ou origem. O carregador `fazenda_cv.monitoring_annotations.load_monitoring_annotations` valida referências, caixas e intervalos.

## Caixas MOT do MooTrack360

O pacote público `TrackEval_evaluation_code.zip` fornece caixas e IDs temporários por quadro. `read_mot_boxes` lê as caixas MOT e exige que a escala para o vídeo decodificado seja informada. Na inspeção do primeiro quadro de `1hour_annotated_sequence.mp4`, as três caixas do quadro 1 alinharam visualmente aos três bovinos centrais ao usar `coordinate_scale=2`. Os metadados `seqinfo.ini` declaram 2944 × 2944, iguais ao MP4, mas as coordenadas das caixas estão aproximadamente na metade da resolução. Confirme a escala em outros quadros antes de uma avaliação completa.

O início do MP4 correspondente foi obtido por requisição parcial em 15/11/2026 e permanece fora do Git. O arquivo MOT tem 53.920 quadros; o MP4 declara cerca de 53.946 quadros e 14,985 FPS, enquanto `seqinfo.ini` declara 10 FPS. Alinhe por número de quadro, sem converter pelo FPS do INI. Essas caixas permitem avaliar detecção e rastreamento no trecho correspondente. Elas **não** fornecem região autorizada nem episódios de alerta; a issue #3 ainda precisa desses rótulos independentes.
