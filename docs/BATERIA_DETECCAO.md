# Bateria de detecção e permanência — #42

Metas locais: revocação >= 60% e permanência após aquisição >= 70%. Uma detecção correta exige correspondência um-para-um com caixa GT, IoU >= 0,5. Revocação = TP/(TP+FN); precisão = TP/(TP+FP), sempre publicada junto de FP e FN. Um bovino nunca detectado continua sendo FN e aparece na cobertura de trajetórias.

Permanência: para cada ID dos rótulos e cada janela, localizar a primeira detecção correta; medir quantas observações visíveis **posteriores** também têm uma caixa corretamente inferida. O primeiro acerto não entra no denominador. IDs nunca detectados não têm permanência mensurável; IDs adquiridos só no último quadro também não contam como 100%. Denominador zero retorna null e não passa o alvo. As janelas são independentes: não se presume continuidade entre quadros 5 e 51.

A agregação soma numeradores e oportunidades, sem média de percentuais. `acquired_tracks`/`labelled_tracks` na agregação contam segmentos de trajetória por janela, não animais únicos. Os resultados por ID estão em cada janela. A taxa auxiliar `consecutive_retention` mede acerto no próximo quadro visível consecutivo após um acerto. Permanência é avaliada por ID GT, sem afirmar reidentificação pelo rastreador do sistema. Nenhuma caixa é retida na tela para pontuar como nova observação.

## Protocolo congelado

- Fonte: prefixo local do `1hour_annotated_sequence.mp4` MooTrack360 e GT do pacote TrackEval. Escala das coordenadas = 2, conforme avaliação anterior. Há três bovinos GT nos trechos iniciais; demais bordas da imagem estão desfocadas.
- Desenvolvimento: quadros 1–5, 51–55 e 101–105, já utilizados em estudos anteriores. Quinze quadros/45 caixas GT; não são dados independentes.
- Variações: Tiny416 e S640, recortes 512/640/736, sobreposição 64 ou 96 e confiança 0,35/0,20/0,10/0,05. Os tamanhos de entrada seguem os respectivos pesos, sem redimensionar o quadro antes dos recortes.
- Reservado: quadros 121–150, sem consulta durante o ajuste desta bateria. Congelar configuração antes de rodar. Mesma câmera e sessão, portanto não equivale a teste externo; duração curta e oclusões insuficientes limitam conclusões.
- Priorizar candidato que cumpra as duas metas, com precisão >= 60% para evitar seleção por excesso de falsos positivos; entre candidatos equivalentes, preferir maior precisão e menor custo. A precisão adicional é um critério de seleção, não substitui a revocação pedida.
- Não reajustar usando o resultado reservado. Se falhar, declarar falha e reservar outra sequência antes de novo ajuste.

O plano de exemplo é `configs/benchmark/development.json`; ajuste os caminhos aos arquivos locais. Execute:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_detection_battery.py \
  configs/benchmark/development.json artifacts/benchmark42/development.json
```

O comando armazena propostas reais com limiar 0,03 e reaplica limiares mais altos sem repetir inferência. O NMS ordena por confiança; propostas de menor confiança não suprimem as de maior confiança. Os arquivos de cache são identificados por hash de pesos, vídeo, recortes, sobreposição e intervalos. Relatórios novos não sobrescrevem os antigos; relatam hashes do vídeo, GT, plano, código das métricas, executor, pesos e cache, além de versões e tempo de inferência. Mídia, cache e relatórios locais ficam fora do Git.

Testes: `PYTHONPATH=src .venv/bin/pytest -q tests/test_detection_benchmark.py`. Cobrem duplicatas, bovino nunca detectado, aquisição no último quadro, lacunas sem detecção, ordenação de quadros e agregação ponderada. O resultado só pode ser declarado atingido para a amostra efetivamente medida; não valida câmera ao vivo, contagem de portão ou meta de 95% em campo.

## Resultados executados em 15/11/2026

| Modelo/recorte | Confiança | TP/FP/FN | Revocação | Precisão | Permanência |
| --- | ---: | --- | ---: | ---: | ---: |
| tiny-512 | 0.35 | 15/0/30 | 33.3% | 100.0% | 100.0% |
| tiny-512 | 0.2 | 18/2/27 | 40.0% | 90.0% | 68.4% |
| tiny-512 | 0.1 | 28/12/17 | 62.2% | 70.0% | 62.5% |
| tiny-512 | 0.05 | 35/15/10 | 77.8% | 70.0% | 84.4% |
| s-512 | 0.35 | 15/2/30 | 33.3% | 88.2% | 78.6% |
| s-512 | 0.2 | 17/9/28 | 37.8% | 65.4% | 92.9% |
| s-512 | 0.1 | 18/20/27 | 40.0% | 47.4% | 100.0% |
| s-512 | 0.05 | 21/25/24 | 46.7% | 45.7% | 60.9% |
| s-640 | 0.35 | 14/5/31 | 31.1% | 73.7% | 91.7% |
| s-640 | 0.2 | 15/9/30 | 33.3% | 62.5% | 68.8% |
| s-640 | 0.1 | 18/15/27 | 40.0% | 54.5% | 57.1% |
| s-640 | 0.05 | 28/19/17 | 62.2% | 59.6% | 69.0% |
| s-736 | 0.35 | 15/6/30 | 33.3% | 71.4% | 78.6% |
| s-736 | 0.2 | 23/11/22 | 51.1% | 67.6% | 90.0% |
| s-736 | 0.1 | 27/14/18 | 60.0% | 65.9% | 87.5% |
| s-736 | 0.05 | 31/18/14 | 68.9% | 63.3% | 88.9% |

O candidato foi congelado após os 16 ensaios: Tiny ONNX, entrada 416, classe 19, recortes 512/64, confiança 0,05 e quatro threads. A seleção priorizou precisão entre os candidatos que cumpriram as metas; nenhum resultado reservado participou da seleção.

Na avaliação reservada (121–150), houve **81 TP, 28 FP e 9 FN**, revocação **90.0%**, precisão **74.3%** e permanência **90.7%** (78/86 observações após aquisição). Continuidade de um quadro para o próximo: 93.7%. São 30 quadros, 90 caixas GT e três animais, em cerca de dois segundos da mesma sessão. As metas locais foram cumpridas; não há evidência de generalização para outros currais.

| ID GT | Acertos/visíveis | Permanência após aquisição |
| --- | ---: | ---: |
| 3 | 24/30 | 23/28 (82.1%) |
| 4 | 30/30 | 29/29 (100.0%) |
| 5 | 27/30 | 26/29 (89.7%) |

O arquivo fonte é parcial e o decoder sinalizou NAL incompleta perto do fim do prefixo. Todos os 30 quadros pedidos foram decodificados; o resultado deve ser repetido no arquivo completo antes de homologação. A escala 2 e a referência por índice de quadro seguem a inspeção anterior; FPS do seqinfo e do MP4 divergem, portanto esta bateria não valida relógio original nem duração de eventos de campo.

Os relatórios completos, propostas, IDs e hashes ficam em `artifacts/benchmark42/development_verified.json`, `evaluation.json` e `selected_configuration.json` no checkout com os dados. Os planos versionados de desenvolvimento e avaliação congelada estão em `configs/benchmark/`. Resultados locais não sobrescrevem relatórios anteriores.

O prefixo de vídeo tem SHA-256 `0da17fcb120f252492e76ff1738d2f108ebf45203c06fa26cf0930dd8f484df3`; GT `595cdad9581382da5f3f406b2259f3d6937b1a131f6d677eca5756bdfcabccbd`; pesos Tiny `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7`. Origem dos dados: [MooTrack360](https://zenodo.org/records/20287681). Origem dos pesos: [YOLOX Tiny](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx). Licença específica dos pesos continua pendente na #4; nenhum peso é incluído nesta PR.

## Reproduzir o perfil no CV

```bash
PYTHONPATH=src .venv/bin/python -m fazenda_cv \
  --source datasets/mootrack360/annotated_prefix.mp4 \
  --model models/yolox_tiny.onnx --input-size 416 --class-id 19 \
  --detection-only --max-width 0 --tile-size 512 --tile-overlap 64 \
  --confidence-threshold 0.05 --cpu-threads 4 \
  --annotated artifacts/candidato.avi --run-report artifacts/candidato.json
```

O perfil é específico desta câmera e permanece opt-in. Aplicar 0,05 globalmente em outras cenas pode aumentar falsos positivos; o padrão do aplicativo continua 0,35. Reproduzir os quadros 121–150 no CLI requer início `120/FPS` e duração `30/FPS`, ou usar o avaliador com o plano congelado.

Não foram reduzidos IoU, alterados rótulos, removidos animais difíceis ou inseridas caixas previstas para alcançar as metas. O primeiro teste descartado de continuidade de caixas foi documentado na #38; esta bateria pontua somente caixas produzidas em cada quadro.

## Evidência operacional e revisão visual

O perfil foi executado também pelo CLI real nos mesmos quadros 121–150: 30 quadros, 109 caixas (igual a TP+FP da bateria), máximo de quatro por quadro, zero passagens e 0,69 FPS de processamento nesta CPU. A saída `artifacts/benchmark42/candidate_121_150.avi` mantém os 30 quadros e 2,002 s do vídeo original; o relatório de execução contém os parâmetros. Isso verifica que a varredura por cache e o detector usado pela aplicação produzem o mesmo total de caixas no perfil escolhido.

Uma cópia de apresentação, `candidate_121_150_30fps.mp4`, usa a exportação interpolada da #39. Ela não entra nas métricas. A prancha `revisao_gt_121_135_150.jpg` mostra recortes de revisão dos quadros 121, 135 e 150, com GT amarelo e detecções verdes. A inspeção confirmou alinhamento dos três IDs, acertos, omissões e uma caixa larga indevida sobre animais próximos. O recorte da prancha é apenas visual: a bateria pontuou o quadro completo. A precisão de 74,3% ainda significa 28 falsos positivos; as metas atingidas não eliminam essas falhas.
