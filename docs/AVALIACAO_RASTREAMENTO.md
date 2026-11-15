# Avaliação do rastreador

O rastreador atual associa centróides por distância. Isso é adequado para a demonstração simples, mas pode trocar IDs quando bovinos se cruzam ou ficam ocultos. Use vídeos reais com IDs temporários anotados por quadro para medir continuidade; o ID anotado serve apenas para a sessão de avaliação e não identifica o animal na fazenda.

`score_tracks` compara, por quadro, posições rotuladas e trilhas previstas dentro de uma distância máxima definida antes do teste. O relatório separa posições perdidas, trilhas sem rótulo, trocas de ID e fragmentos após oclusão. A avaliação deve incluir passagens em sentidos opostos, animais lado a lado, oclusões curtas e prolongadas, dia e noite quando disponíveis. Registre a distância de associação, resolução, FPS e limiares.

Compare o rastreador de centróides com um substituto somente se houver erros que afetem contagem, imobilidade ou travessia. Reavalie os eventos finais após qualquer troca.

## Dados reais do MooTrack360

O pacote [TrackEval_evaluation_code.zip](https://zenodo.org/records/20287681) foi baixado em 14/11/2026 (SHA-256 `26800ea3b6e653e4e9d7c54a2587060bd2a920b4e862f0b84afef624234b6478`). Ele contém `gt/gt.txt`, 53.920 quadros de referência a 10 FPS e saídas de oito rastreadores em formato MOTChallenge. A classe `MotPosition` e as funções `read_mot_positions`/`aligned_mot_frames` transformam linhas MOT em posições com IDs temporários, incluindo quadros vazios e IDs que começam em zero.

Para um trecho difícil, foram comparados os quadros 50.000–50.299 em resolução 2944 × 2944. Com distância máxima entre centros de 80 pixels, havia 2.400 posições rotuladas. `score_tracks` mediu:

| Saída publicada | Posições perdidas | Trilhas extras | Trocas de ID | Fragmentos |
| --- | ---: | ---: | ---: | ---: |
| SORT | 1 | 58 | 21 | 1 |
| ByteTrack | 2 | 14 | 4 | 2 |

Esses números são da métrica simples de correspondência por distância deste projeto. Não equivalem a HOTA, IDF1 nem às métricas oficiais do TrackEval, e o resultado muda com o limite de 80 pixels. A comparação comprova que o avaliador lê rótulos e saídas reais; **ainda não mede o nosso `CentroidTracker`**. Para concluir a issue #6, execute o detector e o rastreador próprios sobre o vídeo correspondente, alinhe os quadros ao `gt.txt` e compare seus eventos e trocas de identidade. O vídeo de referência ainda está em download e a associação exata entre sequência e câmera deve ser conferida antes do cálculo.
