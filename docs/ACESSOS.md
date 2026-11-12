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
