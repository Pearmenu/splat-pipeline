# Como filmar o prato (turntable) — roteiro de captura

A qualidade do `.splat` é decidida aqui. 5 minutos montando direito valem mais que
qualquer ajuste depois. O alvo: cobrir o prato de **todos os ângulos**, com foco
nítido, fundo liso e luz constante.

> ⚠️ **LIÇÃO DO 1º TESTE:** o modelo saiu **achatado** (uma panqueca) porque a câmera
> girou numa **só altura**. O 3DGS só reconstrói o que a câmera viu de vários ângulos.
> Pra ter VOLUME e ALTURA, é **obrigatório filmar de 3 alturas diferentes** (de cima,
> meio e rasante). Isso é o item mais importante deste guia — não pule.

## Ajustes do iPhone (Ajustes → Câmera, uma vez)
- **Gravar Vídeo: 4K a 30 fps** (a nitidez da produção vem da resolução; 1080p borra).
- **Formatos → "Mais Compatível"** (H.264, evita o HEVC do iPhone).
- **Vídeo HDR / Dolby Vision: DESLIGADO.**
- **Grade: LIGADA.** · **Lens Correction: LIGADA.**

## No app Câmera, antes de gravar
- Modo VÍDEO, **lente 1x principal** (nunca 0,5x ultra-wide nem telefoto).
- **Toque e segure no prato até "AE/AF LOCK"** (trava foco+exposição — crítico, senão
  a câmera desfoca no meio da volta).
- Prato ocupando ~60–70% da tela, com folga.

## Montagem

- **Bandeja giratória** (dessas de bolo / "lazy susan") com o prato no centro.
- **Câmera fixa** num tripé, apontada pro prato. Quem gira é o prato, não a câmera.
- **Fundo + base VERDE, liso e fosco** (papel/feltro/TNT verde atrás E embaixo). ⚠️ Use
  VERDE (não cinza/preto): o prato é azul e a comida não tem verde, então o recorte por
  cor (`mask.mode: chroma`) remove só o verde e **mantém o prato** — que é o que faltava.
  Sem estampa, sem reflexo, sem bagunça no fundo.
- **Luz difusa e constante**: 2 luzes laterais (ou perto de uma janela com luz
  indireta). Evite flash, sol direto e sombra dura. Nada de luz piscando.

## Como gravar

Grave **2 voltas completas em alturas diferentes** (pare e reposicione a câmera
entre elas):

1. **Volta 1 — rasante**: câmera quase na altura do prato (~10–20° acima da mesa).
   Gira a bandeja devagar, 1 volta completa.
2. **Volta 2 — 45°**: levanta a câmera pra uns 45° olhando pra baixo. Outra volta
   completa.
3. (Opcional) **Volta 3 — quase de cima** (~70°), se o prato tiver detalhe no topo.

Dicas:
- **Devagar**: cada volta ~15–20 s. Giro rápido borra os frames.
- **Câmera travada**: nada de zoom ou foco caçando no meio da volta. Trava o foco.
- **Grave em 4K** (Ajustes → Câmera → Gravar Vídeo → 4K30). A produção é nítida porque
  tem resolução — 1080p deixa os gaussians "borrados". Vídeo na horizontal.
- O prato inteiro sempre no enquadramento, com uma folga nas bordas.

## Resumo (o "checklist")

- [ ] Bandeja giratória + câmera no tripé (câmera parada)
- [ ] Fundo preto/verde liso, embaixo e atrás
- [ ] Luz difusa, constante, sem reflexo forte
- [ ] 2–3 voltas completas em alturas diferentes
- [ ] Giro devagar (~15–20 s/volta), foco travado
- [ ] Total ~30–60 s de vídeo

## O que evitar (some o "limpa")

- Fundo com textura/movimento → vira sujeira no modelo.
- Reflexo forte / vidro / talher muito brilhante → buracos e manchas.
- Mexer a câmera junto com o prato → o SfM se perde.
- Pouca luz / luz mudando → frames borrados, reconstrução fraca.
