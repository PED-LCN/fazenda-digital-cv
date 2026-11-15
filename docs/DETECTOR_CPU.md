# Comparação de detector e CPU — #38

O CLI aceita `--cpu-threads` (padrão 4), controlando threads internas do ONNX Runtime e usando uma thread entre operadores. Isso limita o paralelismo sem alterar detecções. No primeiro quadro anotado, Tiny com recortes 512/64 demorou 6,661 s com uma thread, 3,551 s com duas e 2,020 s com quatro. Medidas únicas, sujeitas à carga/temperatura; não equivalem a benchmark de hardware.

Foi baixado o YOLOX-S ONNX oficial, entrada 640 e classe COCO 19, de https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx. SHA-256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`. O repositório YOLOX usa Apache-2.0; licença específica dos pesos não foi confirmada. Os pesos permanecem locais, não redistribuídos. Use `--model ../cv-monitoring/models/yolox_s.onnx --input-size 640 --cpu-threads 4`.

Com limiar 0,20, recortes S de 736/96, IoU 0,5 e escala MOT 2, nos quadros 1, 51 e 101 do MooTrack360:

| Quadro | TP | FP | FN | Segundos |
| --- | ---: | ---: | ---: | ---: |
| 1 | 2 | 1 | 1 | 3,634 |
| 51 | 1 | 0 | 2 | 3,641 |
| 101 | 2 | 1 | 1 | 3,692 |

No quadro 1 o Tiny 512/64 e limiar 0,20 teve 1 TP, 0 FP e 2 FN. S com quadro inteiro teve zero detecções; recortes 1280 também tiveram cobertura inferior aos 736. São dados de desenvolvimento, usados para escolher parâmetros, sem generalização para outra sessão.

Nos quatro clipes CattleBehaviours6 de 50 quadros cada, S em quadro inteiro teve detecções em 50 quadros de alimentação (Tiny:47), 12 de ruminação deitado (Tiny:5), zero de bebida e zero de ruminação em pé. Não há GT de caixas nesses clipes: esses números não são precisão. O modelo maior melhora alguns casos e mantém falhas importantes; não foi adotado como padrão. A intermitência não foi resolvida e não se preenchem caixas ausentes para fazê-las parecer detecções reais.

A inferência por recortes permanece muito abaixo de 30 FPS nesta CPU. Para inferência contínua em alta taxa, é necessário medir detector adaptado ao enquadramento e hardware acelerado. FPS do arquivo de apresentação é uma propriedade separada. Teste unitário verifica configuração da sessão ONNX; regressões são cobertas pela suíte completa.

Também foi experimentada continuidade por confiança: inicia caixas acima de 0,35 e permite caixas atuais acima de 0,10 sobrepostas às dos dois quadros anteriores, sem inventar caixas ausentes. Nos trechos 1–5 e 51–55, o resultado foi 5 TP/1 FP/10 FN por trecho, contra 5 TP/0 FP/10 FN do Tiny com limiar 0,35. Sem ganho e com falsos positivos extras, a regra experimental foi descartada. Reter caixas por tempo na tela esconderia omissões e não corrigiria detecção; o próximo avanço de precisão depende de pesos adequados ou ajuste fino.
