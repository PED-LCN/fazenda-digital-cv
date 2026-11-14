# Qualificação de pesos para vídeo real

O adaptador atual recebe saída bruta YOLOX em ONNX. O [repositório oficial do YOLOX](https://github.com/Megvii-BaseDetection/YOLOX) publica código e artefatos; sua [licença de código](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE) é Apache-2.0. Confirme separadamente a licença e a origem dos pesos específicos escolhidos. A classe `cow` em COCO é um ponto de partida, não prova de desempenho no curral.

Registre um model card TOML junto dos pesos locais (fora do Git):

```toml
path = "weights.onnx"
source_url = "https://example.org/model"
license = "verificar licença dos pesos"
sha256 = "substituir pelo hash SHA-256 de 64 caracteres"
input_size = 416
cattle_class_id = 19
class_names = ["preencher mapa completo das classes"]
```

O exemplo acima é ilustrativo e não passa na validação até ser preenchido com o mapa completo e o hash real. `load_model_card` verifica procedência declarada, dimensões, índice da classe e SHA-256. Execute o detector com vídeo ou fotos rotuladas do conjunto de avaliação e use `score_frame` para acumular verdadeiros positivos, falsos positivos e falsos negativos por quadro com IoU predefinida. Documente limiar de confiança, resolução, FPS, CPU e memória. Se os pesos exigirem formato diferente da saída bruta YOLOX, abra uma issue de adaptador antes de alegar compatibilidade. Não declare a meta de contagem atingida a partir de métricas de detecção.

Para uma demonstração operacional com vídeo real, execute `fazenda-cv --source trecho.mp4 --model-card modelo.toml --source-id curral-1 --detection-only --max-frames 150 --annotated artifacts/real.avi --run-report artifacts/real.json`. O cartão determina o peso, o tamanho de entrada e a classe bovino. O modo `--detection-only` não desenha a linha nem emite passagens; use-o quando o vídeo não mostrar um acesso calibrado. O relatório registra quadros processados, quadros com detecção, maior número de bovinos num quadro, eventos e FPS de processamento. O campo `validation_level` vale `operational_smoke_test`: essas medidas mostram que o vídeo percorreu a aplicação, mas não medem precisão sem rótulos independentes.

Para a próxima entrega, use um trecho real completo e documente URL, licença, SHA-256, condições de câmera, modelo, comando, relatório e vídeo anotado. Confira visualmente caixas sobre bovinos e erros evidentes. Anotações de avaliação separadas dos dados de ajuste continuam necessárias para concluir a qualificação quantitativa; o ajuste fino dos pesos pode ficar para o sprint seguinte.
