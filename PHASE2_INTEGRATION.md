# Phase 2 — Integração com o PeAR (vídeo → .splat automático)

Fluxo: o admin envia um vídeo do prato → vai pro R2 → dispara um job no RunPod
(GPU) que roda a esteira → o worker sobe o `.splat` (e `.ply`) de volta pro R2 →
o RunPod chama um webhook → o PeAR cria a linha em `models` → o modelo aparece na
lista. O admin acompanha o status em tempo real.

```
SplatVideoUpload (UI)
  → POST /api/splat/submit   (cria job + presign do vídeo)
  → PUT  vídeo no R2
  → POST /api/splat/start    (presign saída + dispara RunPod /run com webhook)
  → GET  /api/splat/job/[id] (polling até ready/error)
RunPod worker (serverless/handler.py)
  → baixa vídeo, roda pipeline.py, sobe .splat/.ply pros presigned PUT
  → RunPod POSTa o resultado em /api/splat/webhook
        → cria linha em public.models, marca job 'ready'
```

## Ligar/desligar (a flag única)

Tudo é controlado por **uma flag** (duas metades: servidor + cliente):

```bash
SPLAT_PIPELINE_ENABLED=true              # habilita as rotas /api/splat/*
NEXT_PUBLIC_SPLAT_PIPELINE_ENABLED=true  # mostra o botão no admin
```

Pôr qualquer valor diferente de `true` (ou remover) **desativa** sem quebrar nada:
as rotas respondem 404 e o botão some. Os dados/arquivos já gerados continuam
funcionando normalmente (são linhas em `models` como qualquer outra).

## Setup (uma vez)

1. **Worker no RunPod:**
   ```bash
   # na pasta splat-pipeline/ (num host com Docker):
   docker build -t pear-splat .
   docker build -f serverless/Dockerfile.serverless -t pear-splat-serverless .
   # push pear-splat-serverless pro seu registry; crie um Serverless Endpoint
   # no RunPod apontando pra essa imagem (GPU 4090/L40S).
   ```
2. **Banco:** rode `migrations/001_splat_jobs.sql` no Supabase.
3. **Env no PeAR:**
   ```bash
   SPLAT_PIPELINE_ENABLED=true
   NEXT_PUBLIC_SPLAT_PIPELINE_ENABLED=true
   RUNPOD_API_KEY=...
   RUNPOD_SPLAT_ENDPOINT_ID=...          # id do endpoint serverless
   # (NEXT_PUBLIC_SITE_URL precisa ser a URL pública pro webhook do RunPod chegar)
   ```

## Remover de vez

Apague (nada mais depende):
- `pear-viewer/lib/splat/`
- `pear-viewer/app/api/splat/`
- `pear-viewer/components/splat/`
- o bloco `<SplatVideoUpload/>` + o import/flag em `app/admin/models/page.tsx`
- as 4 linhas de env no `.env.example`
- `drop table public.splat_jobs cascade;`

A tabela `models` e o resto do app ficam intactos.

## Notas

- Os `.splat` gerados vão pro **R2** (helper `lib/r2.ts` já existente), não pro
  Supabase Storage onde estão os splats enviados à mão. O viewer abre por URL, então
  tanto faz; o `splat_url` aponta pro R2 público.
- O webhook é autenticado por um `callback_token` por job (na URL). Dá pra
  endurecer depois validando também a assinatura nativa do RunPod.
- Ainda **não testado ponta a ponta** — depende do endpoint RunPod no ar.
