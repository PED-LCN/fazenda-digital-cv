# Fazenda Digital - monitor de passagens

Protótipo local para contar bovinos em um corredor de manejo a partir de vídeo, abrir alertas de horário/divergência e conservar os eventos enquanto a conexão estiver indisponível. Ainda não é uma validação zootécnica nem um modelo treinado para a fazenda.

## Requisitos

- Linux x86_64 ou ARM64, Python 3.12, FFmpeg e uma câmera RTSP ou arquivo de vídeo.
- Para começar sem câmera, `--demo` gera uma cena sintética contínua com objetos verdes. Esse modo testa a tubulação, não detecta bovinos reais.
- Para inferência, forneça um modelo ONNX YOLOX com saída padrão `[1, anchors, 5 + classes]`, classes COCO ou modelo próprio com mapa documentado. Os pesos não entram no Git.

## Instalação e execução

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
fazenda-cv --source ./caminho/video.mp4 --model ./models/bovinos.onnx
```

Sem modelo, `--demo` identifica marcadores verdes em vídeo ou gera uma cena sintética se não houver `--source`:

```bash
fazenda-cv --demo
```

Sem `--source`, a API sobe em estado ocioso e pode receber quadros por uma integração futura. Abra `http://127.0.0.1:8000`. O painel usa SQLite em `./data/fazenda-cv.sqlite3`.

Para disponibilizar o painel na rede local, defina `FARM_CV_HOST=0.0.0.0`, `FARM_CV_USERNAME` e `FARM_CV_PASSWORD` com valores próprios. A aplicação recusa exposição na rede sem credenciais. Para uma instalação real, use TLS no gateway/proxy e restrinja o acesso à rede do curral.

Variáveis opcionais: `FARM_CV_DATABASE`, `FARM_CV_DATA_DIR`, `FARM_CV_EVIDENCE_RETENTION_DAYS` (padrão 7), `FARM_CV_ERP_EVENTS_URL`, `FARM_CV_ERP_TOKEN`, `FARM_CV_MODEL`, `FARM_CV_CATTLE_CLASS_ID`, `FARM_CV_CAMERA_SOURCE`, `FARM_CV_FARM_ID`, `FARM_CV_CAMERA_ID`, `FARM_CV_TIMEZONE` (padrão `America/Sao_Paulo`), `FARM_CV_LINE_START_X/Y`, `FARM_CV_LINE_END_X/Y` (coordenadas de 0 a 1; esquerda para direita é entrada), `FARM_CV_HOST`, `FARM_CV_PORT`, `FARM_CV_USERNAME`, `FARM_CV_PASSWORD`.

## Sessão de manejo e eventos

Cada sessão recebe a quantidade esperada de passagens, o horário permitido e uma linha de contagem normalizada. Os eventos de entrada e saída são mantidos separadamente. Ao encerrar a sessão, a contagem total é comparada à quantidade esperada; eventos fora do horário e divergências geram alerta local. O SQLite conserva sessão e eventos após reinício. Uma imagem JPEG por evento é retida localmente por sete dias (configurável); não há gravação contínua. O adaptador atual da sirene é simulado: equipamento físico só deve ser ligado depois de definir relé, alimentação e limites de acionamento.

O evento JSON tem `schema_version`, `event_id`, `farm_id`, `camera_id`, `session_id`, `event_type`, `direction`, `occurred_at`, `confidence`, `model_version` e `details`. O envio opcional ao ERP usa HTTPS e `Idempotency-Key`; eventos só saem da fila depois de resposta 2xx. O endpoint deve tratar a chave de forma idempotente.

## Limites conhecidos

- O adaptador ONNX implementa a saída YOLOX padrão; outros formatos exigem outro adaptador.
- Pesos e classes precisam ser validados e licenciados individualmente. Nenhum modelo vem embutido.
- O modo `--demo` não é ground truth nem evidência de desempenho em curral.
- RTSP, sirene física, clipes de evidência, reconexão da câmera e sincronização ERP precisam de homologação com os equipamentos/endpoint reais.
- O binário Godot entregue não inclui o projeto-fonte acessível, então sua simulação ainda não foi integrada.

## Desenvolvimento

```bash
pytest
ruff check .
```

Use commits pequenos e mensagens no formato `feat:`, `fix:`, `test:`, `docs:`. Não comite imagens, vídeos, credenciais ou pesos. Antes de adotar um modelo para distribuição, registre licença do código, dos pesos e dos dados de treinamento.
