# Preparação para gravações reais: monitoramento e movimentação

Este documento prepara duas frentes independentes sobre a ferramenta local atual. Ele não declara precisão em campo nem ativa alertas ou integração. A captura Godot validou o caminho de vídeo até eventos; o detector por cor do simulador não serve para imagens reais. O adaptador real existente aceita YOLOX ONNX, mas o repositório não distribui pesos.

## Frentes e entregas iniciais

| Frente | Entrada | Primeira entrega | Fora do primeiro ciclo |
| --- | --- | --- | --- |
| Monitoramento geral | Câmera fixa do curral, área autorizada e regiões configuradas | Ocupação por região; alertas revisáveis de aglomeração, imobilidade prolongada, travessia para fora e presença fora da área | Diagnóstico de saúde e alerta automático de queda |
| Movimentação | Acessos do curral e da ordenha, cada um com câmera/fonte, linha e sentido próprios | Eventos de passagem e totais de entradas e saídas por acesso e sessão | Identificação individual de bovinos |

A queda será estudada em uma investigação com trechos rotulados e métricas; não será apresentada como funcionalidade validada antes disso. O primeiro sinal de comportamento anômalo é imobilidade prolongada, sujeito a revisão humana.

## Dados e validação antes de implementar regras

1. Criar um manifesto para cada foto ou vídeo público: identificador local, URL de origem, autor, licença e condições de uso, data de obtenção, tipo de mídia, ambiente, câmera/ângulo quando conhecido, resolução, FPS e duração para vídeos, iluminação, oclusão e divisão `ajuste`/`avaliação`. Registrar o SHA-256 do arquivo. Guardar mídia em `datasets/` ou `videos/`, já ignorados pelo Git; não incluir URLs com credenciais.

O manifesto CSV pode ser lido com `fazenda_cv.media_manifest.load_manifest`. Exemplo ilustrativo de linha (não corresponde a uma mídia obtida):

```csv
media_id,media_type,source_url,author,license,usage_terms,sha256,environment,split,duration_seconds,fps,width,height,lighting,occlusion
curral_exemplo,video,https://example.org/video.mp4,Autor Exemplo,CC BY 4.0,Atribuição obrigatória,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,curral,tuning,12.5,25,1920,1080,dia,parcial
```

O CSV do exemplo é apenas um modelo de preenchimento: confirme a licença da mídia real e substitua o hash pelo SHA-256 do arquivo obtido. Para fotos, `duration_seconds` e `fps` ficam vazios. `split` aceita `tuning` e `evaluation`.
2. Manter rótulos separados por tarefa. Para movimentação: acesso, instante no vídeo, sentido e casos ambíguos. Para monitoramento: caixas de bovinos nos quadros amostrados, regiões, intervalos de aglomeração/imobilidade, travessias do limite e presença fora da área. Fotos servem para detecção, mas não comprovam eventos temporais.
3. Separar ajuste e avaliação por vídeo, sessão ou origem, evitando quadros do mesmo vídeo nos dois conjuntos. Publicar apenas manifesto e métricas compatíveis com a licença; reter arquivos e rótulos que não possam ser redistribuídos fora do Git.
4. Registrar para cada modelo candidato origem, licença, classes, formato de saída, dimensão de entrada, SHA-256 e configuração de inferência. Verificar compatibilidade real com o adaptador YOLOX antes de executar o pipeline.
5. Medir detecção, passagens por acesso, falsos alertas, omissões, trocas de rastreamento, latência, FPS, CPU e memória. Repetir no hardware candidato e, quando houver, com gravações locais. A meta documental de 95% para contagem só pode ser afirmada quando sustentada pelo conjunto real de avaliação, inclusive nas condições relevantes de luz e oclusão.

## Sequência técnica

1. Preparar corpus, rótulos, modelo licenciado e avaliação de referência.
2. Tornar sessões e posição temporal do vídeo reproduzíveis. Hoje `occurred_at` de arquivo é ancorado ao horário do replay; o novo registro deve conservar o deslocamento no arquivo e só usar horário absoluto de captura quando conhecido.
3. Testar o rastreador de centróides com vários animais e oclusões. Substituí-lo apenas se a avaliação mostrar perdas ou trocas que afetem passagens, imobilidade ou travessias.
4. Implementar as duas frentes sobre detecção e rastreamento compartilhados. Configurações e resultados permanecem separados por `source_id`, área e acesso; uma gravação não deve misturar totais do curral com os da ordenha.
5. Acordar contrato de integração com o outro projeto e só então ativar publicação por webhook. O consumidor deve deduplicar por `event_id` porque retentativas podem repetir a entrega.

## Contrato candidato para integração

A saída de passagem `schema_version: 1` do CLI continua disponível. Para novos eventos, a issue de contrato definirá uma versão que distinga `passage`, `occupancy`, `crowding`, `immobility`, `boundary_exit` e `outside_area`. O envelope candidato contém `event_id`, `schema_version`, `event_type`, `source_id`, `session_id`, `occurred_at` quando há horário de captura confiável, `video_offset_ms` para gravações, `area_id` ou `access_id`, e dados específicos do evento. Não inferir identidade individual a partir de `track_id`: ele só vale dentro da sessão e da fonte. O payload final, autenticação do webhook, retentativas e tratamento de falhas serão fechados com o projeto consumidor antes da implementação.

## Portões de aceite

- O corpus tem origem/licença e divisão de avaliação rastreáveis.
- Cada issue funcional traz testes sintéticos e, quando depende de visão real, métricas em vídeos rotulados que não foram usados no ajuste.
- Alertas mostram fonte, área, instante/posição no vídeo e regra disparada para revisão; não são tratados como diagnóstico.
- Webhook tem contrato versionado, entrega com retentativa persistente e teste com receptor controlado; falha de rede não interrompe a análise do vídeo.

Consulte também [VALIDACAO.md](VALIDACAO.md) para o protocolo já existente de contagem em corredor.
