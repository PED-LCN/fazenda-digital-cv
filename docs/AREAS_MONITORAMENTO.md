# Áreas de monitoramento por câmera

Crie um JSON fora da pasta `artifacts/` se quiser versionar a calibração. Cada `source_id` representa uma câmera ou enquadramento fixo. Os pontos são frações da largura e altura da imagem, entre `0` e `1`, em ordem ao redor do polígono. A área autorizada marca o curral; as regiões nomeadas representam locais de observação dentro da cena.

```json
{
  "sources": [
    {
      "source_id": "curral-1",
      "authorized_area": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
      "regions": [
        {"region_id": "bebedouro", "polygon": [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4], [0.2, 0.4]]}
      ]
    }
  ]
}
```

Para conferir a calibração, execute com `--source-id curral-1 --areas-config areas.json --preview` ou grave com `--annotated revisao.avi`. A linha amarela representa o limite autorizado e as linhas azuis, as regiões. O arquivo anotado permite conferir se os polígonos continuam alinhados após a redução de resolução por `--max-width`. A função `NormalizedPolygon.locate()` distingue ponto dentro, fora e na borda para as regras futuras de ocupação e evasão.

O desenho dos polígonos é apenas uma calibração visual. Para validar os pontos na câmera real, compare o vídeo anotado com o enquadramento original, revise mudanças de posição ou zoom e registre a configuração de cada fonte. Polígonos não calculam ocupação nem emitem alertas nesta etapa.
