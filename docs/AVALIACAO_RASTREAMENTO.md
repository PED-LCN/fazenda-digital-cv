# Avaliação do rastreador

O rastreador atual associa centróides por distância. Isso é adequado para a demonstração simples, mas pode trocar IDs quando bovinos se cruzam ou ficam ocultos. Use vídeos reais com IDs temporários anotados por quadro para medir continuidade; o ID anotado serve apenas para a sessão de avaliação e não identifica o animal na fazenda.

`score_tracks` compara, por quadro, posições rotuladas e trilhas previstas dentro de uma distância máxima definida antes do teste. O relatório separa posições perdidas, trilhas sem rótulo, trocas de ID e fragmentos após oclusão. A avaliação deve incluir passagens em sentidos opostos, animais lado a lado, oclusões curtas e prolongadas, dia e noite quando disponíveis. Registre a distância de associação, resolução, FPS e limiares.

Compare o rastreador de centróides com um substituto somente se houver erros que afetem contagem, imobilidade ou travessia. Reavalie os eventos finais após qualquer troca. Ainda não há vídeos reais rotulados para publicar números de campo.
