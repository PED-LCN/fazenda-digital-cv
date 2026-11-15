# Avaliação do rastreador

O rastreador atual associa centróides por distância. Isso é adequado para a demonstração simples, mas pode trocar IDs quando bovinos se cruzam ou ficam ocultos. Use vídeos reais com IDs temporários anotados por quadro para medir continuidade; o ID anotado serve apenas para a sessão de avaliação e não identifica o animal na fazenda.

`score_tracks` compara, por quadro, posições rotuladas e trilhas previstas dentro de uma distância máxima definida antes do teste. O relatório separa posições perdidas, trilhas sem rótulo, trocas de ID e fragmentos após oclusão. A avaliação deve incluir passagens em sentidos opostos, animais lado a lado, oclusões curtas e prolongadas, dia e noite quando disponíveis. Registre a distância de associação, resolução, FPS e limiares.

Compare o rastreador de centróides com um substituto somente se houver erros que afetem contagem, imobilidade ou travessia. Reavalie os eventos finais após qualquer troca.

## Dados reais do MooTrack360

O pacote [TrackEval_evaluation_code.zip](https://zenodo.org/records/20287681) foi baixado em 14/11/2026 (SHA-256 `26800ea3b6e653e4e9d7c54a2587060bd2a920b4e862f0b84afef624234b6478`). Ele contém `gt/gt.txt`, 53.920 quadros de referência e saídas de oito rastreadores em formato MOTChallenge. A classe `MotPosition` e as funções `read_mot_positions`/`aligned_mot_frames` transformam linhas MOT em posições com IDs temporários, incluindo quadros vazios e IDs que começam em zero.

Para um trecho de comparação, foram usados os quadros 50.000–50.299 em resolução 2944 × 2944. Com distância máxima entre centros de 80 pixels, havia 2.400 posições rotuladas. `score_tracks` mediu:

| Saída publicada | Posições perdidas | Trilhas extras | Trocas de ID | Fragmentos |
| --- | ---: | ---: | ---: | ---: |
| SORT | 1 | 58 | 21 | 1 |
| ByteTrack | 2 | 14 | 4 | 2 |

Esses números são da métrica simples de correspondência por distância deste projeto. Não equivalem a HOTA, IDF1 nem às métricas oficiais do TrackEval, e o resultado muda com o limite de 80 pixels. A comparação comprova que o avaliador lê rótulos e saídas reais; **não mede o nosso `CentroidTracker`**. O início de `1hour_annotated_sequence.mp4` foi obtido em 15/11/2026; o vídeo completo de 18,9 GB ainda não foi baixado. O ZIP amostral de 11,5 GB é outra sequência e não pode ser usado com este ground truth.

Há divergências nos metadados: `seqinfo.ini` declara 10 FPS e 2944 × 2944, enquanto o MP4 informa `15000/1001` FPS (aproximadamente 14,99) e 2944 × 2944. As caixas MOT alinham aos bovinos do primeiro quadro quando suas coordenadas são multiplicadas por 2. Confirme escala e indexação em mais trechos antes de converter quadro em milissegundos. Os resultados MOT publicados acima usam somente números de quadro, sem conversão temporal.

## Ensaio do rastreador próprio com posições reais

O arquivo `gt.txt` também permite um ensaio controlado do `CentroidTracker`: a cada quadro, seus centros são entregues ao rastreador como detecções ideais, **sem os IDs dos rótulos**. O avaliador usa os IDs somente depois, para medir continuidade. Assim, qualquer erro medido é de associação do rastreador, mas a ausência de erro não comprova desempenho com o detector real.

```bash
.venv/bin/python scripts/evaluate_mot_tracker.py \
  datasets/mootrack360/mot/gt.txt \
  --first-frame 1 --last-frame 53920 \
  --tracker-distance 100 --max-missed-frames 12 --match-distance 80
```

Resultado local: 350.272 posições em 53.920 quadros; 0 posições perdidas, 0 trilhas extras, 0 trocas de ID e 0 fragmentos. O arquivo tem apenas 8 IDs únicos, com no máximo 8 bovinos por quadro. Entre posições consecutivas do mesmo ID, a mediana do deslocamento é 0 px/quadro, o percentil 90 é 1 px/quadro e o maior deslocamento é 13,34 px/quadro. Esse trecho é pouco exigente para associação por distância; **o resultado não autoriza substituir a avaliação com o detector e o vídeo originais**, nem sustenta 100% de precisão em ambiente real. Passagens, cruzamentos e oclusões ainda precisam de gravações específicas.

Um ensaio separado de inferência no vídeo amostral fixo da mesma fonte encontrou 0 detecções em 20 quadros com YOLOX Tiny e quadro reduzido a 960 px. Em um quadro nativo de 2944 px, o detector também encontrou 0 bovinos na imagem inteira, mas encontrou 2 caixas ao dividir a imagem em 16 recortes de 736 px. Isso sugere investigar inferência por recortes para bovinos pequenos; as duas caixas ainda não foram comparadas com rótulos independentes. O vídeo amostral e o `gt.txt` pertencem a sequências diferentes.

## Ensaio integral no trecho correspondente

O script abaixo executa YOLOX Tiny com recortes e o `CentroidTracker` no início do MP4 correspondente ao `gt.txt`. Os IDs dos rótulos são usados somente na pontuação, não na inferência.

```bash
.venv/bin/python scripts/evaluate_real_tracker.py \
  datasets/mootrack360/annotated_snapshot.mp4 \
  datasets/mootrack360/mot/gt.txt \
  models/yolox_tiny.onnx \
  --first-frame 1 --last-frame 20 --coordinate-scale 2 \
  --tile-size 736 --tile-overlap 96
```

Em 20 quadros, havia 60 posições rotuladas. O fluxo encontrou 11, perdeu 49, produziu 0 trilhas extras, 0 trocas de ID e 1 fragmento, com distância de correspondência de 80 px. A revocação de 18,3% mostra que a limitação dominante nesse trecho é a detecção; zero trocas de ID em apenas 11 correspondências não valida continuidade do rastreador. O trecho foi usado para ajustar a estratégia de recortes, não é avaliação independente. Ainda faltam passagens e oclusões suficientes para decidir sobre substituição do rastreador e impacto em alertas.

Nos quadros 101–120, separados do ajuste inicial, o mesmo fluxo perdeu as 60 posições rotuladas, sem produzir trilhas. A revocação foi 0. Esse resultado impede qualquer conclusão favorável sobre continuidade: primeiro é necessário melhorar a detecção nesta câmera, então repetir a avaliação de identidade e dos eventos.

Com recortes menores de 512 px e sobreposição 64 px, o fluxo encontrou 20 das 60 posições dos quadros 101–120 e perdeu 40, sem trilhas extras, trocas de ID ou fragmentos nesse trecho. A melhora ainda deixa 66,7% das posições sem trilha; os quadros 101–120 foram usados para escolher essa configuração e não servem mais como avaliação final intocada. O custo do detector foi 0,74 FPS no vídeo amostral desta máquina. A decisão sobre substituir o rastreador deve esperar um detector com revocação suficiente e gravações de cruzamentos e passagens.
