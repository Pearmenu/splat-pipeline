# Próxima rodada — passo a passo (já otimizado)

Depois do 1º teste, a esteira está mais rápida (masking na GPU) e à prova de tropeços.
Siga na ordem:

## 0. Antes (no Mac)
- **GitHub Desktop → Push origin** (pra subir as melhorias).
- **Gravar o vídeo turntable** seguindo o `CAPTURA.md` — ⚠️ **3 alturas** (de cima,
  meio, rasante), senão o modelo sai achatado de novo.

## 1. Pod
- RunPod → Pods → Deploy → template **Runpod Pytorch 2.4.0**, GPU **RTX 4090**, disco 40 GB.
- Connect → **Jupyter Lab** → New → **Terminal**.

## 2. Instalar (~8 min)
```bash
git clone https://github.com/Pearmenu/splat-pipeline.git
cd splat-pipeline
bash scripts/setup_pod.sh
```

## 3. Mandar o vídeo (use runpodctl, NÃO o Jupyter — ele trunca)
No **Mac** (terminal), uma vez: `brew install runpod/runpodctl/runpodctl`
Depois: `runpodctl send ~/Downloads/SEU_VIDEO.mov` → ele dá um código.
No **pod**:
```bash
mkdir -p data && cd data && runpodctl receive <CÓDIGO> && cd ..
ls -la data/    # confirme o tamanho (igual ao do Mac)
```

## 4. Rodar (1 comando — ~10-15 min)
```bash
bash run.sh data/SEU_VIDEO.mov
```
Acompanhe os estágios. No `[mask]` confira a linha `rembg providers ativos:` —
tem que aparecer **CUDAExecutionProvider** (se aparecer só CPU, me avise).

## 5. Ver o resultado
Baixe `data/run/out/model.splat` (Jupyter: botão direito → Download — download
funciona normal) e abra em **https://superspl.at/editor** (arrasta o arquivo).

## 6. Ajuste fino (se precisar, sem refazer o treino)
Edite os limiares em `config.yaml` (seção `cleanup`) e rode só a limpeza:
```bash
bash run.sh data/SEU_VIDEO.mov --from-stage cleanup
```

## 7. Ao terminar
- RunPod → **Stop** no pod (pra não gastar crédito).
