# Backlog para gravações reais

Issues publicadas em `PED-LCN/fazenda-digital-cv`. Os identificadores B, I, M e F organizam as dependências; cada título aponta para sua issue no GitHub. Cada item cobre uma responsabilidade. A implementação das funcionalidades não faz parte desta preparação.

## Base

### B1 — [Base] Catalogar fotos e vídeos reais com origem e licença ([#1](https://github.com/PED-LCN/fazenda-digital-cv/issues/1))

**História:** Como equipe de CV, quero registrar a procedência de cada mídia real para saber o que pode ser usado e reproduzir a avaliação.

**Aceite:**
- Manifesto contém origem, autor, licença/condições de uso, SHA-256, ambiente e divisão ajuste/avaliação.
- Para vídeos, registra duração, FPS, resolução, iluminação e oclusão quando conhecidos.
- Mídia e credenciais permanecem fora do Git; há exemplo de preenchimento.

**Depende de:** nenhuma.

### B2 — [Base] Anotar passagens nos vídeos reais ([#2](https://github.com/PED-LCN/fazenda-digital-cv/issues/2))

**História:** Como avaliador, quero marcar cada passagem para medir entradas e saídas por acesso.

**Aceite:**
- Cada passagem tem vídeo, acesso, posição temporal, sentido e indicação de ambiguidade.
- Instruções definem passagem e revisão de discordâncias.
- Rótulos de avaliação são separados dos vídeos de ajuste.

**Depende de:** B1.

### B3 — [Base] Anotar cenas de monitoramento do curral ([#3](https://github.com/PED-LCN/fazenda-digital-cv/issues/3))

**História:** Como avaliador, quero rotular bovinos e ocorrências para medir ocupação e alertas.

**Aceite:**
- Quadros selecionados têm caixas de bovinos e regiões identificadas.
- Trechos têm intervalos de aglomeração e imobilidade, travessias do limite e presença externa, incluindo casos negativos.
- Fotos são usadas somente para detecção; eventos temporais usam vídeos.

**Depende de:** B1.

### B4 — [Base] Qualificar pesos bovinos para vídeo real ([#4](https://github.com/PED-LCN/fazenda-digital-cv/issues/4))

**História:** Como operador, quero um detector real rastreável para avaliar imagens de curral sem usar o detector do Godot.

**Aceite:**
- Origem, licença, classes, formato, dimensão de entrada e SHA-256 dos pesos estão registrados.
- Compatibilidade com o adaptador YOLOX ONNX é demonstrada; se outro formato for necessário, abrir issue própria para o adaptador.
- Precisão e revocação no conjunto real de avaliação são relatadas sem alegar validação de campo.

**Depende de:** B1, B3.

### B5 — [Base] Preservar sessão e posição temporal de gravações ([#5](https://github.com/PED-LCN/fazenda-digital-cv/issues/5))

**História:** Como consumidor de eventos, quero localizar um resultado no vídeo original mesmo após múltiplos replays.

**Aceite:**
- O processamento de arquivo identifica a sessão e o deslocamento temporal no vídeo.
- Horário absoluto de captura só aparece quando conhecido; horário do replay não se passa pelo da gravação.
- Teste reproduz o mesmo arquivo em horários diferentes e verifica posições temporais iguais.

**Depende de:** nenhuma.

### B6 — [Base] Avaliar o rastreador com múltiplos bovinos ([#6](https://github.com/PED-LCN/fazenda-digital-cv/issues/6))

**História:** Como equipe de CV, quero medir trocas de trilha e perdas para decidir se o rastreador atual serve às duas frentes.

**Aceite:**
- Avaliação inclui cruzamentos, oclusões e animais próximos em vídeos rotulados.
- Relatório mede trocas de identidade, fragmentação e impacto em passagens e alertas.
- Se o rastreador de centróides falhar, o critério de substituição e o comparativo com o novo adaptador são registrados.

**Depende de:** B3, B4.

## Integração

### I1 — [Integração] Definir contrato versionado dos eventos ([#7](https://github.com/PED-LCN/fazenda-digital-cv/issues/7))

**História:** Como sistema consumidor, quero um contrato estável para diferenciar passagens, ocupação e alertas.

**Aceite:**
- Esquema documenta tipos, IDs, fonte, sessão, área/acesso, tempo e dados específicos.
- Exemplos válidos e deduplicação por `event_id` estão documentados; `track_id` não é identidade permanente.
- Contrato é validado com o outro projeto e preserva a leitura do JSON de passagem v1 do CLI.

**Depende de:** B5.

### I2 — [Integração] Publicar eventos com webhook confiável ([#8](https://github.com/PED-LCN/fazenda-digital-cv/issues/8))

**História:** Como sistema consumidor, quero receber eventos mesmo quando a rede oscila.

**Aceite:**
- URL e credencial são configuráveis sem entrar no Git.
- Fila local persistente retenta falhas sem bloquear a análise; reenvios conservam `event_id`.
- Teste com receptor controlado cobre sucesso, indisponibilidade, reinício e deduplicação.

**Depende de:** I1.

## Monitoramento geral

### M1 — [Monitoramento] Configurar áreas delimitadas ([#9](https://github.com/PED-LCN/fazenda-digital-cv/issues/9))

**História:** Como operador, quero delimitar curral e regiões de observação para interpretar cada câmera.

**Aceite:**
- Polígonos normalizados por `source_id` representam área autorizada e regiões monitoradas.
- Configuração inválida é rejeitada e a prévia mostra os limites sobre o vídeo.
- Teste cobre pontos dentro, fora e na borda.

**Depende de:** B1.

### M2 — [Monitoramento] Medir ocupação por área ([#10](https://github.com/PED-LCN/fazenda-digital-cv/issues/10))

**História:** Como operador, quero acompanhar quantos bovinos aparecem em cada região ao longo do vídeo.

**Aceite:**
- Série temporal registra contagem por região, fonte e posição no vídeo.
- Regra de inclusão de um bovino na região é documentada e testada.
- Resultado é comparado aos quadros reais rotulados.

**Depende de:** B3, B4, B5, M1.

### M3 — [Monitoramento] Alertar aglomeração ([#11](https://github.com/PED-LCN/fazenda-digital-cv/issues/11))

**História:** Como operador, quero saber quando muitos bovinos permanecem juntos em uma região.

**Aceite:**
- Limite de quantidade ou densidade e duração mínima são configuráveis por região.
- Um episódio contínuo gera alerta com regra, região e evidência temporal, sem disparo por quadro.
- Falsos alertas e omissões são medidos em trechos rotulados.

**Depende de:** M2, I1.

### M4 — [Monitoramento] Alertar imobilidade prolongada ([#12](https://github.com/PED-LCN/fazenda-digital-cv/issues/12))

**História:** Como operador, quero revisar bovinos que permanecem quase sem deslocamento por tempo configurado.

**Aceite:**
- Janela temporal e deslocamento máximo são configuráveis; perda de trilha não vira prova de imobilidade.
- Alerta inclui fonte, região, trecho e regra, sem diagnóstico de saúde.
- Casos positivos e negativos em vídeo rotulado são avaliados.

**Depende de:** B3, B5, B6, M1, I1.

### M5 — [Monitoramento] Alertar travessia para fora da área ([#13](https://github.com/PED-LCN/fazenda-digital-cv/issues/13))

**História:** Como operador, quero revisar uma trajetória que cruza o limite autorizado para fora.

**Aceite:**
- Um cruzamento observado gera um evento por trilha e episódio, com direção para fora.
- Oscilação próxima da borda não gera alertas repetidos.
- Testes cobrem entrada, saída, tangência e perda de trilha.

**Depende de:** B5, B6, M1, I1.

### M6 — [Monitoramento] Alertar presença fora da área ([#14](https://github.com/PED-LCN/fazenda-digital-cv/issues/14))

**História:** Como operador, quero detectar bovino fora da área mesmo quando a travessia não aparece na gravação.

**Aceite:**
- Presença externa confirmada por duração configurável gera alerta distinto da travessia.
- Um episódio contínuo não dispara a cada quadro; retorno e nova ocorrência podem gerar novo evento.
- Casos positivos e negativos em vídeo rotulado são avaliados.

**Depende de:** B3, B4, B5, M1, I1.

### M7 — [Monitoramento] Investigar detecção de queda ([#15](https://github.com/PED-LCN/fazenda-digital-cv/issues/15))

**História:** Como equipe de CV, quero verificar se quedas podem ser distinguidas de deitar e oclusões antes de prometer um alerta.

**Aceite:**
- Conjunto de trechos positivos e negativos tem origem/licença e rótulos revisados.
- Experimento relata precisão, revocação, falsos positivos e limitações por condição de câmera.
- Decisão de avançar ou não para alerta operacional é documentada; nenhum alerta é ativado nesta issue.

**Depende de:** B1, B3, B4.

## Movimentação

### F1 — [Movimentação] Configurar os acessos do curral e da ordenha ([#16](https://github.com/PED-LCN/fazenda-digital-cv/issues/16))

**História:** Como operador, quero identificar cada passagem física para não misturar curral e ordenha.

**Aceite:**
- Curral e ordenha têm `access_id`, `source_id`, linha e orientação de entrada independentes.
- Prévia mostra a linha e o sentido de cada acesso; configuração inválida é rejeitada.
- Não há suposição de que ambas as passagens apareçam na mesma câmera.

**Depende de:** B2.

### F2 — [Movimentação] Registrar passagens por acesso ([#17](https://github.com/PED-LCN/fazenda-digital-cv/issues/17))

**História:** Como operador, quero um evento por cruzamento válido no acesso correspondente.

**Aceite:**
- Eventos distinguem `in` e `out` por acesso e incluem sessão/posição temporal.
- Debounce evita duplicidade por oscilação na linha; `track_id` não vira ID do bovino.
- Erros de contagem por acesso são medidos nos vídeos rotulados.

**Depende de:** B2, B4, B5, B6, F1, I1.

### F3 — [Movimentação] Consultar totais por acesso e sessão ([#18](https://github.com/PED-LCN/fazenda-digital-cv/issues/18))

**História:** Como operador, quero ver entradas e saídas do curral e da ordenha separadamente.

**Aceite:**
- Totais são derivados dos eventos por `access_id` e `session_id`, sem misturar fontes.
- Reprocessar ou reenviar o mesmo `event_id` não altera os totais.
- Testes cobrem sessões distintas, os dois acessos e vídeo sem passagens.

**Depende de:** F2.
