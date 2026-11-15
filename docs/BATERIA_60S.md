# Bateria local na gravação real de 60 segundos

Executada em 15/11/2026 sobre `datasets/mootrack360/farm1_area1_60s_2fps.mp4`,
2944 × 2944, 120 quadros a 2 FPS. A fonte está disponível localmente e contém
movimento real de animais; não é uma animação de PNGs. O derivado
`artifacts/mootrack360_60s_tiled.avi` é dessa cena. `artifacts/apresentacao.mp4`
mostra o simulador Godot e não integra esta avaliação.

O MP4 de 60 segundos é derivado do prefixo local da sequência amostral Farm1
Area1 do [MooTrack360](https://zenodo.org/records/20287681), com licença informada
CC BY-NC-SA 4.0. O GT publicado no pacote TrackEval corresponde a outra sequência;
não foi reutilizado nesta cena.

## Referência e limites

Foram desenhadas por inspeção visual do assistente 31 referências por quadro em
nove instantes: 0, 10, 20, 30, 35, 40, 45, 50 e 59,5 segundos. As caixas e IDs são
**provisórios e exigem conferência humana independente**. Não são rótulos oficiais
dos autores. A área externa desfocada não permite reconhecer todos os animais.
Os rótulos incluem corpos parcialmente ocultos na região nítida, sem tratar
cabeças ou patas como animais adicionais.

Os três primeiros instantes servem para ajuste; os seis seguintes para avaliação.
Após observar a falha inicial, houve nova rodada de ajuste nos mesmos três
instantes e reavaliação nos seis seguintes. A segunda medição é regressão na mesma
cena, não um teste cego em outra sessão.

O acerto usa IoU >= 0,5, associação um-para-um ordenada por confiança, e mantém
animais nunca detectados no denominador da revocação. Permanência significa
acertos nas observações amostradas visíveis após a primeira aquisição, excluindo
o acerto inicial. Não mede continuidade nos 120 quadros nem a identidade atribuída
pelo rastreador. Não há pares de quadros consecutivos anotados nesta amostra.

## Resultados

Foram testadas 39 combinações: nove perfis de modelo, recortes e rotações com
variação de limiar. Pesos YOLOX Tiny 416 e S 640; recortes 512, 736, 1024 e 1280;
rotações 0/90/180/270 graus; quatro threads; propostas a partir de 0,03.
Seleção por cumprimento das duas metas globais, seguida de F1 e permanência,
usando apenas os três quadros de ajuste em cada rodada.

| Rodada | Configuração escolhida | TP / FP / FN | Revocação | Precisão | Permanência amostrada |
| --- | --- | --- | --- | --- | --- |
| Inicial | S, recortes 1280/256, confiança 0,05 | 69 / 74 / 117 | 37,10% | 48,25% | 54/65 = 83,08% |
| Reavaliação | S, recortes 1280/256, quatro rotações, confiança 0,03 | 117 / 265 / 69 | 62,90% | 30,63% | 92/117 = 78,63% |

Na reavaliação, seis das 31 referências nunca tiveram correspondência. A
permanência global acima de 70% não significa que cada animal atingiu essa meta:
consulte `tracks` no relatório. A baixa precisão e as duplicatas tornam o perfil
com confiança 0,03 inadequado para ativar contagem ou alertas sem revisão. Os
parâmetros experimentais não alteram os padrões do aplicativo.

## Refinamento de duplicatas

Mais 48 combinações foram avaliadas sobre as propostas já calculadas: limiar,
NMS de 0,25 a 0,50 e supressão opcional de fragmentos contidos em caixas maiores.
O filtro foi escolhido nos quadros de ajuste; não houve alteração de rótulos nem
do IoU mínimo de acerto. São 87 combinações no total.

O candidato escolhido usou NMS 0,45, confiança 0,03 e desabilitou a remoção por
contenção. Na reavaliação obteve 112 TP, 236 FP e 74 FN: revocação 60,22%, precisão
32,18% e permanência amostrada 87/116 = 75,00%. Reduzir duplicatas não resolveu a
qualidade. Estes valores são globais; não cumprem a meta por animal nem substituem
referência humana ou teste contínuo. Quatro testes de supressão passaram.

`refine_duplicates.py`, `dedup_development.json`, `dedup_frozen.json`,
`dedup_regression.json` e `test_duplicate_refinement.py` ficam junto dos demais
artefatos. O vídeo integral conserva as predições do candidato anterior à
supressão adicional para permitir comparação reproduzível.

## Evidências e reprodução

No checkout com os dados, `artifacts/battery60/` contém:

- `run_sampled_battery.py` e `run_second_round.py`: executores reproduzíveis locais.
- `development.json` e `development_v2.json`: todas as combinações e métricas.
- `evaluation.json` e `regression_v2.json`: pontuação e resultados por referência.
- `frozen.json` e `frozen_v2.json`: configurações escolhidas antes de cada pontuação.
- `parameter_sweep.csv`: comparação tabular das 39 combinações.
- `reference_*.jpg`: caixas de referência para revisão, sem predições.
- `baseline_review_*.jpg`: referência amarela e predições verdes.
- `provenance.json`: hashes de fonte, rótulos e pesos.
- `render_full_sequence.py`: inferência dos 120 quadros, sem carregar caixas antigas.
- `candidate_full_events.jsonl`: caixas atuais e posição no vídeo por quadro; log
  experimental de detecção, não contrato de passagens ou webhook.
- `candidate_full_60s.avi`, `full_progress.json` e `full_run.json`: vídeo de revisão,
  progresso e conclusão do processamento integral. Confirmar `status: completed`
  antes de considerar o vídeo pronto.

Os rótulos ficam em `datasets/mootrack360/local_review_60s.json`. Para repetir,
use outro diretório de resultados, preservando os relatórios existentes, com
`PYTHONPATH` apontando ao `src` da branch #42 ou #44 e o ambiente virtual com ONNX.
Os executores locais possuem caminhos absolutos para o checkout com os dados.

SHA-256 da fonte: `0c6ef452302812ba91f341a446a4853c8652e3fee563f71735f82a01b71adaa4`.
SHA-256 dos rótulos: `2f4547e307301d95e02b43860c418ac837b2bf1cdcce32d05f4e35b141b40877`.

Testes do pontuador: cinco casos passaram. A transformação inversa das caixas em
quatro rotações foi verificada com coordenadas conhecidas em imagem não quadrada.

## Aceite pendente

Conferir os rótulos com uma pessoa, anotar quadros consecutivos, medir continuidade
e associação de IDs, reduzir falsos positivos e avaliar outra sessão. Esta bateria
aproveita o minuto local; não substitui o ensaio de 30 minutos nem permite fechar
issues de precisão, rastreamento, passagem ou alertas.

## Evidência complementar com rótulos oficiais já disponíveis

A checagem do processo da ETH confirmou que `video3.mp4` e `video4.mp4` já foram
extraídos por inteiro enquanto o pacote de 8,26 GB continuava baixando. O processo
nativo estava ativo; consultas de processos dentro do ambiente restrito não o
enxergavam. O estado anterior de download parado não descrevia esse processo.

Uma leitura consistente, somente leitura, do checkpoint SQLite de `video3`
produziu os seguintes resultados. O detector já estava congelado pelo ajuste no
`video1`: YOLOX-S 640, recortes 1280/128, confiança 0,20, quatro threads. Estes
números não usam as referências provisórias da imagem olho de peixe.

| Recorte do checkpoint | Quadros | TP / FP / FN | Revocação | Precisão | Permanência |
| --- | --- | --- | --- | --- | --- |
| Primeiro minuto | 901 | 2573 / 1384 / 3555 | 41,99% | 65,02% | 62,93% |
| Snapshot de 6 min 26,5 s | 5800 | 19402 / 6651 / 25678 | 43,04% | 74,47% | 45,55% |

Os relatórios são `official_first_60_seconds.json` e
`official_committed_snapshot.json`; o executor é
`summarize_available_official.py`, em `artifacts/battery60/`. O checkpoint original
continua independente e não foi alterado. Os números do snapshot ficam fixos no
relatório mesmo quando o processo avança. O pacote completo ainda precisa da
verificação de integridade; os 30 minutos não terminaram de ser avaliados.

A retenção condicional de um quadro para o próximo foi alta (98,37% no primeiro
minuto), mas não substitui a permanência após aquisição: longas ausências de
animais previamente detectados continuam penalizadas. Esta evidência reforça que
as duas metas não estão cumpridas de maneira geral.
