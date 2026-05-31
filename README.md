# PeAR Splat Pipeline

Esteira **100% automática** que transforma um vídeo de um prato em um modelo
3D Gaussian Splatting limpo, pronto pro menu do PeAR.

```
vídeo → frames → máscara (recorta o prato) → poses (SfM) → treino 3DGS
      → limpeza (poda floaters) → export .splat (+ .ply)
```

O resultado é um `.splat` (canônico, leve, rápido no celular) e um `.ply`
(arquivo/teste). O visualizador do PeAR (`@mkkellogg/gaussian-splats-3d`)
abre os dois — usamos `.splat` em produção por ser ~10x menor.

---

## Por que roda na nuvem (NVIDIA), não no Mac

COLMAP, GLOMAP e gsplat dependem de **CUDA**. Apple Silicon não roda CUDA, então
o processamento pesado precisa de uma GPU NVIDIA. Recomendado: **RunPod** com uma
**RTX 4090** ou **L40S** (~5–10 min/prato, centavos de dólar por prato).

## Requisito de captura (pro modo automático ser confiável)

A poda automática só fica determinística com input previsível:

- **Turntable**: prato na bandeja giratória, câmera fixa no tripé.
- 2 alturas (rasante + ~45°), 1–2 voltas completas, ~20–40s de vídeo, 4K.
- **Fundo liso e fosco** (preto ou verde), luz difusa, sem reflexo forte.

Sem esse padrão, a máscara automática erra de vez em quando e o arquivo sai sujo.

---

## Como rodar (num pod RunPod com GPU)

```bash
# 1. build da imagem (uma vez)
docker build -t pear-splat .

# 2. processa um vídeo
docker run --gpus all -v $PWD/data:/data pear-splat \
  --video /data/prato.mp4 \
  --workdir /data/prato_run

# saída: /data/prato_run/out/model.splat  e  model.ply
```

Sem Docker (deps já instaladas no host):

```bash
python pipeline.py --video data/prato.mp4 --workdir data/prato_run
```

Rodar só uma etapa (debug):

```bash
python pipeline.py --video ... --workdir ... --from-stage train
```

## Estágios

| # | Estágio        | Ferramenta            | Saída                          |
|---|----------------|-----------------------|--------------------------------|
| 1 | extract_frames | ffmpeg + OpenCV       | frames nítidos                 |
| 2 | mask           | rembg (BiRefNet)      | prato recortado + máscaras     |
| 3 | sfm            | COLMAP + GLOMAP       | poses de câmera                |
| 4 | train          | gsplat (MCMC)         | modelo 3DGS (.ply)             |
| 5 | cleanup        | numpy/scipy           | floaters/outliers podados      |
| 6 | convert        | —                     | .splat + .ply final            |

Parâmetros em [`config.yaml`](config.yaml).

## Status

Phase 1 — protótipo. **Ainda não testado em GPU** (precisa de um pod NVIDIA).
Os pontos mais prováveis de precisar de ajuste por versão de ferramenta:
a instalação de COLMAP/GLOMAP no `Dockerfile` e os flags do `simple_trainer.py`
do gsplat em [`stages/train.py`](stages/train.py). Tudo está modular pra ser
ajustado estágio a estágio.
