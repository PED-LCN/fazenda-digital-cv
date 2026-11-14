# Fontes candidatas para demonstração com vídeo real

| Fonte | Uso nesta entrega | Limite relevante |
| --- | --- | --- |
| [CattleBehaviours6](https://zenodo.org/records/23064957) | Clipe curto e sem sobreposição de predições para mostrar leitura de vídeo e detecção | 1.905 clipes rotulados por comportamento; não há rótulos de passagem nem caixas por quadro declarados no registro. A licença não aparece no campo `Rights` da página; conferir os metadados/arquivo antes de redistribuir. |
| [Cow Tracking by Classification](https://github.com/meiqing-wang/Cow-TrackingbyClassification) | Referência de arquitetura e GIFs para inspeção qualitativa | Código Apache-2.0, mas os GIFs já mostram caixas e identidades previstas. O modelo publicado usa YOLOv8 e classificação de indivíduos; não encaixa diretamente no adaptador YOLOX ONNX nem demonstra entradas/saídas. Os pesos estão em Google Drive. |
| [MooTrack360](https://zenodo.org/records/20287681) | Avaliação futura de detecção/rastreamento sob oclusão e iluminação variável | Vídeo anotado de 1 hora e modelos publicados, mas o pacote total tem 199 GB, imagens olho de peixe e fluxo de referência orientado a CUDA. O repositório dos autores informa CC BY-NC-SA 4.0. |

## Escopo da demonstração

Um vídeo real processado com pesos YOLOX ONNX, saída anotada e `--run-report` comprova funcionamento técnico da leitura, inferência e gravação. O relatório operacional registra detecções e FPS, mas **não** comprova precisão de contagem, classificação de comportamento ou eventos de evasão. Para medir essas funcionalidades serão necessários vídeos com passagens/ocorrências anotadas e câmera semelhante à do projeto.

Arquivos de mídia e pesos ficam em `datasets/`, `videos/` e `models/`, ignorados pelo Git. Registre hashes e URLs originais antes de reproduzir os resultados. Não publique cópia dos vídeos sem licença confirmada. O ajuste fino do detector fica para o próximo sprint após medir os erros no material real.
