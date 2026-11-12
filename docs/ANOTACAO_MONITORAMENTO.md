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
