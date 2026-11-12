# Anotação de passagens

Use somente vídeos listados no manifesto de mídia. Para cada bovino, anote o instante em que o centro do corpo cruza a linha do acesso. `in` significa entrada na área correspondente, e `out` significa saída. Registre `curral` e `ordenha` separadamente. Quando o sentido ou a travessia não puder ser visto com segurança, marque `ambiguous=true`; esses casos exigem revisão e não entram na métrica principal de contagem.

O CSV usa os cabeçalhos `media_id,access_id,video_offset_ms,direction,ambiguous`. Exemplo ilustrativo:

```csv
media_id,access_id,video_offset_ms,direction,ambiguous
clip_1,curral,1200,in,false
clip_1,ordenha,2400,out,true
```

O carregador `fazenda_cv.passage_annotations.load_passage_annotations` verifica o vídeo no manifesto, a duração, os dois acessos, os sentidos e duplicatas. Dois revisores devem conferir passagens ambíguas e registrar a decisão de consenso. Separe vídeos por sessão/origem entre ajuste e avaliação; não use quadros do mesmo vídeo nos dois conjuntos.
