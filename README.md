# Fazenda Digital — ferramenta local de visão computacional

Este módulo recebe quadros de uma janela Godot, arquivo de vídeo ou câmera RTSP, detecta objetos, acompanha trajetórias e emite **somente eventos de passagem**. Ele não inicia servidor nem oferece página web. Outro sistema pode consumir os eventos JSON do `stdout`, ler um arquivo JSONL ou chamar `CvPipeline.process()` em Python.

```
janela Godot / vídeo / RTSP → detector substituível → rastreador → linha → eventos JSON
                                                              ↘ vídeo anotado opcional
```

## Preparar o ambiente

Requer Python 3.12. Para a demonstração Godot em Linux, também requer FFmpeg, `xprop` e uma sessão X11 ou XWayland. `ffplay` é opcional para prévia ao vivo.

```bash
cd cv-monitoring
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
```

O perfil travado inclui ONNX Runtime e ferramentas de teste. Uma instalação apenas do núcleo pode usar `pip install -e .`; para inferência real, `pip install -e '.[onnx]'`.

## Demonstração com o executável fornecido

```bash
.venv/bin/fazenda-cv \
  --godot ../ttttttttttttttttttttttttttttttttttttttttttt.x86_64 \
  --simulator --preview \
  --events artifacts/passagens.jsonl \
  --annotated artifacts/apresentacao.avi
```

O comando abre o Godot e captura **somente a janela do simulador**. No jogo, use **Spawn Vacas**, **Porteira** e **Passar Porteira** para produzir movimento. O terminal mostra objetos visíveis, entradas e saídas; `--preview` mostra as caixas e a linha em tempo real, e o AVI pode ser reproduzido após encerrar com `Ctrl+C`. O modo simulador reconhece o corpo cinza das vacas dessa cena por cor; não usa esse critério em vídeo de fazenda. A linha padrão fica sobre a abertura da porteira observada no vídeo (`--line 0.34 0.32 0.34 0.13`). Ajuste os quatro valores normalizados com `--line X1 Y1 X2 Y2` se mudar o enquadramento.

O exemplo supõe que o executável esteja na pasta ao lado do repositório. Em outro computador, informe seu caminho em `--godot`.

Para desenhar a linha sobre a porteira, instale a variante gráfica do OpenCV no ambiente virtual e acrescente `--draw-line` ao comando acima:

```bash
.venv/bin/python -m pip uninstall -y opencv-python-headless
.venv/bin/python -m pip install 'opencv-python>=4.10,<5'
```

Com `--draw-line`, o Godot e a janela de monitoramento abrem juntos. Avance até o curral; na janela de monitoramento pressione **L**, arraste o mouse para desenhar a linha sobre a imagem ao vivo e pressione **Enter**. **Q** encerra a espera. A contagem e a gravação anotada começam após a confirmação. O terminal imprime os quatro valores de `--line` para reutilização. A captura da janela solicita 30 FPS por padrão; para ajudar o computador a acompanhar, experimente `--width 640 --height 360 --max-width 640` e retire `--annotated` se não precisar gravar. O terminal mostra a taxa efetiva de processamento. Reduzir a resolução pode fazer perder vacas pequenas, então confira a contagem com o vídeo apresentado.

Se a captura da janela não estiver disponível no computador de apresentação, grave o executável com o recurso `--write-movie` do Godot e processe o AVI com `--source arquivo.avi --simulator`. A gravação requer interação com o jogo e driver gráfico funcional. [Godot: gravação de filmes](https://docs.godotengine.org/en/4.7/tutorials/animation/creating_movies.html), [FFmpeg: captura de janela X11](https://www.ffmpeg.org/ffmpeg-devices.html#x11grab).

## Trocar pela câmera real

```bash
.venv/bin/fazenda-cv \
  --source 'rtsp://camera/stream' \
  --model ./models/bovinos.onnx \
  --source-id corredor-1 \
  --line 0.5 1 0.5 0 \
  --events artifacts/passagens-reais.jsonl
```

A fonte muda sem alterar o rastreamento, a contagem ou o contrato de eventos. O detector real espera um modelo **YOLOX ONNX com saída bruta** e classe bovino 19 no mapa COCO por padrão; `--class-id` e `--input-size` permitem ajustar outro modelo compatível. O pré-processamento segue a [demonstração oficial de YOLOX para ONNX Runtime](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/demo/ONNXRuntime/onnx_inference.py). Nenhum peso está incluído. O identificador do detector registra parte do SHA-256 dos pesos usados. Antes da distribuição, registre também origem e licença dos pesos e dos dados. Trocar a entrada pela câmera não comprova a qualidade das detecções: serão necessários pesos licenciados, ajuste da linha, vídeo real anotado e medição em campo.

Para hardware mais limitado, comece com `--fps 5 --width 640 --height 360` na captura da janela e `--max-width 640` em vídeo ou RTSP; compare perda de passagens e latência antes de reduzir ainda mais. A prévia e a gravação anotada são opcionais.

## Contrato de saída

Cada linha do `stdout` ou de `--events` é um objeto JSON independente:

```json
{"source_id":"corredor-1","direction":"out","occurred_at":"2026-10-21T03:18:02+00:00","confidence":1.0,"detector_version":"simulator-gray-cow-1","track_id":1,"event_id":"b57cfc99-af30-4174-97ac-5aef92f9365a","schema_version":1}
```

`event_id` permite deduplicação pelo consumidor. `occurred_at` está em UTC. Em vídeo gravado, o intervalo entre quadros segue o FPS do arquivo, ancorado ao instante do replay. A confiança `1.0` do detector da simulação representa uma regra de cor, não uma probabilidade calibrada. A integração externa fica responsável por sessões, total esperado, alertas, armazenamento e ERP.

## Validação e limites

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
```

Um hook Git executa esses comandos antes de cada commit e o fluxo de CI repete os testes. Vídeos, modelos, eventos locais e credenciais ficam fora do Git.

Os testes cobrem detecção da cena simulada, contagem nos dois sentidos, reprodução de AVI até JSON e vídeo anotado, e formato de entrada do adaptador YOLOX. Neste ambiente, a captura da janela Godot foi verificada com curral vazio (80 quadros, zero contagens) e com duas vacas visíveis; uma reprodução com a porteira produziu uma passagem. Isso demonstra a integração, não precisão em fazenda. Sobreposição de animais, mudança de ângulo e câmera RTSP ainda exigem avaliação com dados reais.

O procedimento e as métricas para essa avaliação estão em [docs/VALIDACAO.md](docs/VALIDACAO.md).

As duas frentes planejadas para gravações reais, o protocolo de dados e as dependências de implementação estão em [docs/PREPARACAO_GRAVACOES_REAIS.md](docs/PREPARACAO_GRAVACOES_REAIS.md).

As histórias pequenas e os links das issues no GitHub estão em [docs/BACKLOG_GRAVACOES_REAIS.md](docs/BACKLOG_GRAVACOES_REAIS.md).

Para demonstrar o detector com gravação real e gerar um relatório de execução, veja [docs/QUALIFICACAO_MODELO.md](docs/QUALIFICACAO_MODELO.md).

A comparação dos conjuntos públicos considerados está em [docs/FONTES_VIDEO_REAL.md](docs/FONTES_VIDEO_REAL.md).

O registro de pesos candidatos e a medição de caixas estão em [docs/QUALIFICACAO_MODELO.md](docs/QUALIFICACAO_MODELO.md).
