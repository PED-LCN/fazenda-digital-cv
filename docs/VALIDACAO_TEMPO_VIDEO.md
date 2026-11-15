# Validação da posição temporal em gravação real

Em 14/11/2026 foi usado o clipe `CattleBehaviours6/feeding/00062.mp4` do [CattleBehaviours6](https://zenodo.org/records/23064957), extraído localmente do ZIP. O arquivo tem SHA-256 `8e8b1fbda3856f2c72955361f2fcb5dd7206af1ecbfb6f05e233f0e106917eed`, 50 quadros, 5 FPS e duração de 10 segundos. A mídia permanece fora do Git.

`OpenCVSource` leu o arquivo duas vezes. Em ambas as sessões, os deslocamentos começaram em `0, 200, 400` ms e terminaram em `9800` ms; as sequências dos 50 deslocamentos foram iguais e os `session_id` foram diferentes. Todos os quadros usaram `time_basis: replay`. Uma execução com YOLOX Tiny produziu eventos de teste contendo `session_id`, `video_offset_ms` e `time_basis: replay` nos deslocamentos 4600, 7000 e 9200 ms. O vídeo mostra alimentação, sem acesso calibrado: esses eventos não representam passagens válidas; servem somente para conferir os campos temporais.

O teste cobre arquivo de FPS constante. Em vídeo de FPS variável, é necessário comparar os timestamps originais do contêiner antes de afirmar que o deslocamento calculado por índice/FPS representa o instante exato. A licença da mídia não está declarada no campo de direitos do registro Zenodo; não redistribuir o clipe sem confirmação.
