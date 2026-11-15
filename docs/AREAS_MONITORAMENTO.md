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

## Ensaio com vídeo real

Em 15/11/2026, `--areas-config` foi executado no primeiro quadro do vídeo MooTrack360 `1hour_annotated_sequence.mp4`, reduzido de 2944 × 2944 para 960 × 960. A saída AVI continha um quadro; a inspeção visual confirmou que os dois polígonos foram desenhados na posição e escala esperadas. A configuração local do ensaio delimitava aproximadamente a parte superior da baia e uma região interna, **apenas para verificar a sobreposição técnica**. Ela não representa o limite autorizado de um curral do projeto nem deve ser usada para alertas. A calibração física por câmera e a revisão pelo operador continuam pendentes na issue #9.
