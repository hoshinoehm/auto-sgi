# Deploy no EasyPanel — AUTO SGI API

## Pré-requisitos

- VPS Hostinger com EasyPanel rodando
- Repositório Git com o código (GitHub, GitLab, etc.)
- n8n já instalado no EasyPanel

---

## Passo 1 — Subir o código para um repositório Git

O EasyPanel faz o build direto do repositório. Certifique-se de que o `.gitignore`
está correto e que o `.env` **nunca** foi commitado.

```bash
git init
git add .
git commit -m "feat: auto-sgi api inicial"
git remote add origin https://github.com/SEU_USUARIO/auto-sgi.git
git push -u origin main
```

---

## Passo 2 — Criar o serviço no EasyPanel

1. No EasyPanel, clique em **+ New Service**
2. Escolha **App**
3. Preencha:
   - **Name:** `auto-sgi-api`
   - **Source:** GitHub (conecte sua conta)
   - **Repository:** seu repositório
   - **Branch:** `main`
   - **Build Method:** `Dockerfile`

---

## Passo 3 — Configurar variáveis de ambiente

No EasyPanel, na aba **Environment** do serviço, adicione:

```
SGI_USUARIO=2645349
SGI_SENHA=sua_senha_real_aqui
API_KEY=cole_aqui_a_chave_gerada
DATA_DIR=/data
HEADLESS=true
CHROME_BIN=/usr/bin/chromium
CHROMEDRIVER_PATH=/usr/bin/chromedriver
SELENIUM_TIMEOUT=30
PYTHONUNBUFFERED=1
```

Para gerar a API_KEY, rode no seu computador:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Passo 4 — Configurar o Volume

Na aba **Volumes** do serviço:

| Campo | Valor |
|---|---|
| Host Path | `/etc/easypanel/projects/auto-sgi/data` |
| Container Path | `/data` |

Isso garante que os arquivos (DOCX, XLSX, controle, logs) sobrevivem
a restarts e deploys.

---

## Passo 5 — Configurar a Porta (somente interna)

Na aba **Ports**:
- **Port:** `8000`
- **Expose:** **NÃO ative** (o serviço não precisa de domínio público)

O n8n acessa internamente pelo nome do serviço: `http://auto-sgi-api:8000`

> Se o EasyPanel perguntar por domínio, deixe em branco ou desative.

---

## Passo 6 — Deploy

Clique em **Deploy**. O EasyPanel vai:
1. Clonar o repositório
2. Executar o `docker build` usando o `Dockerfile`
3. Subir o container
4. Verificar o healthcheck em `/health`

O build leva ~3-5 minutos na primeira vez (baixa o Chromium).

---

## Passo 7 — Verificar se está funcionando

No terminal da VPS (ou via SSH):

```bash
# Testa o health diretamente pelo IP interno
curl http://auto-sgi-api:8000/health

# Ou pelo IP da VPS com a porta (se tiver exposto temporariamente)
curl http://localhost:8000/health
```

Resposta esperada:
```json
{"status": "ok", "timestamp": "...", "data_dir": "/data"}
```

---

## Passo 8 — Configurar o n8n para acessar a API

No n8n, nos nós **HTTP Request**, use:

- **URL:** `http://auto-sgi-api:8000/extrair-escala`
- **Header:** `X-API-Key: sua_chave_api`

> O nome `auto-sgi-api` deve ser exatamente o nome do serviço no EasyPanel.
> Ambos (n8n e auto-sgi-api) precisam estar no mesmo projeto EasyPanel
> para compartilhar a rede interna Docker.

---

## Atualizar o serviço (deploy de nova versão)

```bash
# No seu computador: commit e push
git add .
git commit -m "fix: corrige seleção de turno"
git push

# No EasyPanel: clique em Deploy no serviço auto-sgi-api
# Os arquivos em /data NÃO são apagados (volume persistente)
```

---

## Rollback

No EasyPanel, na aba **Deployments**, selecione uma versão anterior
e clique em **Redeploy**.

---

## Estrutura de dados no servidor após o deploy

```
/etc/easypanel/projects/auto-sgi/data/
├── entradas/      ← DOCX enviados pelo n8n
├── extraidas/     ← XLSX gerados
├── controle/      ← controle.xlsx (fonte da verdade)
├── logs/          ← logs de execução
└── resultado/     ← relatórios JSON
```

Você pode acessar esses arquivos via SFTP direto na VPS.
