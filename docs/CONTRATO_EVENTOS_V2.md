# Contrato candidato de eventos v2

Este contrato prepara integração futura com outro projeto. O CLI continua emitindo passagem `schema_version: 1`; o envelope v2 ainda não é publicado por webhook. O consumidor deve validar este contrato antes de ativarmos a entrega.

Exemplo de passagem em gravação:

```json
{
  "schema_version": 2,
  "event_id": "4e4cc930-ec0b-462a-a6f0-92ff4ae6a53d",
  "event_type": "passage",
  "source_id": "camera-curral",
  "session_id": "sessao-1",
  "occurred_at": "2026-11-12T12:00:00+00:00",
  "time_basis": "replay",
  "video_offset_ms": 1200,
  "access_id": "curral",
  "data": {"direction": "in", "confidence": 0.8, "detector_version": "modelo-1", "track_id": 3}
}
```

Tipos: `passage` usa `access_id`; `occupancy`, `crowding`, `immobility`, `boundary_exit` e `outside_area` usam `area_id`. Todos carregam `source_id`, `session_id`, `event_id`, `occurred_at`, `time_basis` e `data`. Em replay, `video_offset_ms` é obrigatório e `occurred_at` indica o processamento, não a data original da gravação. Em fonte ao vivo, o deslocamento pode faltar. `track_id` identifica apenas uma trilha naquela fonte e sessão; não é identidade do bovino. Retentativas preservam `event_id`, e o consumidor deduplica por esse campo.

Antes da integração, o outro projeto deve revisar formato, autenticação, semântica de horários, retenção, retentativas e tratamento de versões desconhecidas. A issue #8 cuidará da entrega por webhook.
