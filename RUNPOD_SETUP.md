# RunPod — passo a passo

Dois momentos: **Parte A** valida a esteira (Fase 1) num pod normal com um prato
real. **Parte B** sobe o endpoint serverless e liga no PeAR (Fase 2). Faça A antes
de B — não adianta automatizar antes de ver um `.splat` bom saindo.

---

## Parte A — Validar a esteira num GPU Pod

Objetivo: rodar `pipeline.py` num vídeo de verdade e abrir o `.splat` no seu viewer.

1. **Criar o pod.** RunPod → Pods → Deploy → GPU **RTX 4090** (ou L40S).
   Template: **RunPod PyTorch 2.x** (já vem CUDA + conda). Disco: ~40 GB.
   Abra o **Web Terminal** (ou conecte via SSH).

2. **Subir o código + um vídeo.** No terminal do pod:
   ```bash
   git clone <seu-repo> splat-pipeline   # ou suba a pasta via runpodctl/scp
   cd splat-pipeline
   ```
   Coloque um vídeo turntable de teste em `data/prato.mp4` (use o upload do
   Jupyter do template, `runpodctl send`, ou `wget <url>`).

3. **Instalar as dependências** (sem Docker):
   ```bash
   bash scripts/setup_pod.sh
   ```

4. **Rodar a esteira:**
   ```bash
   GSPLAT_DIR=/opt/gsplat python pipeline.py \
     --video data/prato.mp4 --workdir data/run
   ```
   Saída em `data/run/out/model.splat` e `model.ply`.

5. **Conferir no seu viewer.** Baixe o `.splat` (`runpodctl receive` ou Jupyter) e
   abra no visualizador do PeAR. É aqui que a gente calibra a poda no `config.yaml`
   (Fase 3) até ficar limpo.

> Se algo falhar, é quase sempre (a) COLMAP/GLOMAP sem variante CUDA — veja o
> comentário no `setup_pod.sh`; ou (b) flags do `simple_trainer.py` mudaram de
> versão — rode `python /opt/gsplat/examples/simple_trainer.py mcmc --help` e
> ajuste `stages/train.py`.

---

## Parte B — Endpoint Serverless + ligar no PeAR

### B1. Buildar a imagem serverless

**Opção recomendada (sem Docker no seu Mac): build pelo GitHub.**
- Garanta que `splat-pipeline/` está num repo Git acessível.
- RunPod → Serverless → New Endpoint → **Import Git Repository**.
- Repo = seu repo; **Dockerfile path** = `serverless/Dockerfile.serverless`;
  **build context** = a pasta `splat-pipeline/`.
- RunPod builda a imagem (CUDA + COLMAP/GLOMAP + gsplat) sozinho.

**Opção alternativa (se tiver um host Linux amd64 com Docker):**
```bash
cd splat-pipeline
docker build -f serverless/Dockerfile.serverless -t SEU_USER/pear-splat-serverless .
docker push SEU_USER/pear-splat-serverless
# crie o endpoint apontando pra essa imagem
```

### B2. Configurar o endpoint
- GPU: **RTX 4090 / L40S**. Workers: min 0, max 1–3 (escala sob demanda).
- **Container Disk**: ~30 GB. **Idle timeout**: ~30 s. **Execution timeout**: 1200 s.
- Copie o **Endpoint ID** (vai no `RUNPOD_SPLAT_ENDPOINT_ID`).
- Em RunPod → Settings → **API Keys**, gere uma key (vai no `RUNPOD_API_KEY`).

### B3. Banco de dados
Rode no Supabase (SQL Editor): o conteúdo de `migrations/001_splat_jobs.sql`.

### B4. Variáveis no PeAR
```bash
SPLAT_PIPELINE_ENABLED=true
NEXT_PUBLIC_SPLAT_PIPELINE_ENABLED=true
RUNPOD_API_KEY=...
RUNPOD_SPLAT_ENDPOINT_ID=...
# NEXT_PUBLIC_SITE_URL precisa ser a URL pública (pro webhook do RunPod chegar)
```
Redeploy o PeAR pra valer as flags.

### B5. Testar
1. Admin → Models → selecione um restaurante → painel **"Gerar .splat a partir de
   um vídeo"** (só aparece com a flag on).
2. Envie um vídeo turntable, dê um nome, **Gerar modelo 3D**.
3. Acompanhe o status (enviando → fila → gerando → pronto). Ao terminar, o modelo
   aparece na lista de Models automaticamente.

**Debug:** RunPod → seu endpoint → **Requests/Logs** mostra cada job e o stderr do
worker. No PeAR, a tabela `splat_jobs` guarda `status`, `error`, `runpod_id`.
