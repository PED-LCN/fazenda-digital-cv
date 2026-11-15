# Acessos de curral e ordenha

Cada acesso tem uma fonte e uma linha próprias. A ordem dos pontos define a orientação: o lado positivo da linha é a **entrada**. A prévia desenha uma seta para esse lado. Configure os dois acessos mesmo quando estiver processando só um deles.

```json
{
  "accesses": [
    {"access_id": "curral", "source_id": "camera-curral", "line": [0.5, 1, 0.5, 0]},
    {"access_id": "ordenha", "source_id": "camera-ordenha", "line": [0.5, 0, 0.5, 1]}
  ]
}
```

Salve o JSON fora de `datasets/` se quiser versionar a configuração sem credenciais. Processamento de exemplo: `fazenda-cv --source video-curral.mp4 --model models/bovinos.onnx --access-config acessos.json --access-id curral`. Repita com o vídeo da ordenha e `--access-id ordenha`. O vídeo e os pesos ficam fora do Git. A atribuição de `access_id` a cada evento será implementada na issue #17.

## Ensaio com imagem real

Em 15/11/2026, o CLI desenhou uma linha e a seta de entrada sobre o primeiro quadro do vídeo MooTrack360 `1hour_annotated_sequence.mp4`, com saída AVI de 960 × 960. A inspeção visual confirmou a sobreposição e a orientação da seta. A linha foi colocada em posição ilustrativa; **não identifica um acesso físico desse vídeo**. O trecho disponível não mostra cruzamento de curral e ordenha. Portanto, a calibração de ambos os acessos e a validação do sentido real continuam pendentes na issue #16.
