# Validação do monitor de passagens

## O que cada etapa comprova

| Etapa | Fonte | Decisão permitida |
| --- | --- | --- |
| Testes locais | Vídeos sintéticos gerados nos testes | Regressões de direção, contrato de evento e gravação anotada |
| Demonstração Godot | Janela do executável fornecido | Captura da janela, detecção dos modelos cinzas e fluxo até JSON |
| Piloto real | Vídeo de câmera fixa anotado manualmente | Precisão de contagem e escolha de modelo, linha e hardware |

O teste Godot não mede precisão no curral. O detector de cor `simulator-gray-cow-1` só pertence ao adaptador do simulador. Na câmera, use um detector com pesos próprios e documentados.

## Preparar o piloto real

1. Fixar uma câmera em um corredor de uma única direção por vez, registrar posição, resolução, FPS, iluminação e campo de visão. Gravar passagens com e sem oclusão, dia e noite, mantendo os vídeos fora do Git.
2. Anotar manualmente cada passagem com instante e direção. Separar vídeos de ajuste e avaliação por dia/sessão para evitar vazamento entre conjuntos.
3. Registrar para cada modelo: fonte e licença dos pesos, mapa de classes, dimensão da entrada, SHA-256, vídeos de ajuste usados e limiar de confiança.
4. Reproduzir cada vídeo com `--source`, `--model`, `--line` e `--events`. Arquivar comando, versão do código, hash do modelo e eventos JSONL junto dos rótulos.
5. Associar eventos aos rótulos por direção e janela temporal definida antes da avaliação. Medir precisão, revocação, falsos positivos, perdas e erro absoluto de contagem por sessão. Medir também latência, FPS, CPU/RAM e falhas de captura RTSP.
6. Repetir o conjunto fechado no hardware candidato. Aceitar o alvo documental de 95% somente se a avaliação real o sustentar em condições diurnas e noturnas.

Se vacas se cruzarem ou ficarem ocultas, o rastreador simples de centróides poderá trocar identidades e causar erros. Substituir esse adaptador por um rastreador adequado e repetir a avaliação antes do piloto. A fonte de vídeo, o detector e o rastreador possuem pontos de substituição independentes; o consumidor externo recebe o mesmo JSON versionado.
