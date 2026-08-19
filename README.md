# RPA de ponto para ERP

O projeto tem três etapas independentes:

1. consulta a API por HTTP Basic Auth;
2. converte a resposta para o arquivo aceito pelo ERP;
3. abre o ERP com Playwright e importa o arquivo.

A separação permite desenvolver no Windows e executar depois no Linux sem alterar
o fluxo da automação.

## Uso diário no Windows

Abra o PowerShell na pasta do projeto e execute o fluxo completo:

```powershell
cd C:\meu_rpa
.\.venv\Scripts\rpa-ponto.exe run
```

Esse único comando consulta a API, gera o próximo AFD, mantém somente o AFD mais
recente, abre o ERP, processa o arquivo, faz logout e atualiza o relatório com os
screenshots de cada etapa.

O relatório pode ser aberto em:

```text
C:\meu_rpa\output\monitor\index.html
```

Para executar apenas partes do processo, use:

```powershell
.\.venv\Scripts\rpa-ponto.exe fetch
.\.venv\Scripts\rpa-ponto.exe import --file .\output\AFD_SEQUENCIAL.txt
.\.venv\Scripts\rpa-ponto.exe report
```

## Preparação no Windows

Requer Python 3.11 ou mais recente.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
Copy-Item .env.example .env
```

Edite `.env` e informe o usuário e a senha da API em campos separados. Não use
aspas e não envie o arquivo `.env` para o Git.

Por padrão, os arquivos são numerados a partir do modelo informado. O primeiro
será `AFD00014003750288104.txt`; cada nova execução usa o maior sequencial já
existente em `output` mais um. Para trocar a base, altere
`AFD_INITIAL_SEQUENCE` no `.env`.

`AFD_KEEP_FILES=1` mantém somente o AFD de maior sequencial dentro de `output`.
A limpeza ocorre depois que o novo arquivo foi gerado com sucesso e não afeta o
arquivo-modelo guardado na raiz do projeto.

## Comandos

Somente buscar e gerar o arquivo:

```powershell
rpa-ponto fetch
```

Abrir o ERP e importar um arquivo já existente:

```powershell
rpa-ponto import --file .\output\arquivo.txt
```

Executar o fluxo completo, da API até a importação no ERP:

```powershell
rpa-ponto run
```

Use `RPA_HEADLESS=false` durante a configuração assistida. Quando o fluxo estiver
estável, mude para `true`.

### Executar sem abrir a janela do navegador

Para executar todo o RPA apenas pelo terminal, configure no `.env`:

```dotenv
RPA_HEADLESS=true
```

O Playwright ainda utiliza o Chromium internamente, mas nenhuma janela é exibida.
O acesso ao ERP, a importação do AFD, o logout, os screenshots, o relatório local
e a publicação na Cloudflare continuam funcionando normalmente.

Depois execute o mesmo comando do fluxo completo:

```powershell
.\.venv\Scripts\rpa-ponto.exe run
```

Para acompanhar visualmente as ações durante testes ou ajustes, altere novamente
para `RPA_HEADLESS=false`.

`RPA_GLOBAL_DELAY_MS=300` define o tempo padrão entre as ações. Para personalizar
uma ação individual, edite `ACTION_DELAYS_MS` em `src/rpa_ponto/timings.py`.
`None` herda o tempo global; um número substitui o global somente naquela ação.
Por exemplo, `"selecionar_arquivo": 2000` espera dois segundos, enquanto
`"preencher_usuario": 0` não adiciona espera depois de preencher o usuário.

## Gravar os passos do ERP

Com `ERP_URL` preenchida no `.env`, execute:

```powershell
.\scripts\record_erp.ps1
```

Faça o processo no navegador aberto e, ao terminar, feche o navegador e o
Playwright Inspector. A gravação será salva localmente como `rpa_recording.py` e
está ignorada pelo Git. Como o gravador pode registrar valores digitados, não
compartilhe esse arquivo antes de substituirmos usuário e senha pelas variáveis
do `.env`.

O fluxo capturado abre o módulo `CCRHP055` e seleciona o tipo `Apuração`. Esses
valores podem ser alterados por `ERP_PROGRAM_CODE` e `ERP_IMPORT_KIND` no `.env`.
`ERP_LOCALE=pt-BR` mantém a interface automatizada em português mesmo quando o
Linux estiver configurado em inglês.
O RPA não encerra uma sessão já ativa por padrão. Para uma conta exclusiva da
automação, `ERP_CLOSE_ACTIVE_SESSIONS=true` permite recuperar automaticamente uma
sessão deixada por uma execução interrompida.

## Migração para Linux

Crie o ambiente virtual, instale o projeto e o Chromium:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m playwright install --with-deps chromium
npm ci
cp .env.example .env
```

O endereço configurado em `ERP_URL` é privado. A máquina Linux precisará estar na
mesma rede, VPN ou rota que alcança o ERP.

Antes de ativar o modo headless, valide uma importação com
`RPA_HEADLESS=false`. Depois, altere para `true` e execute novamente.

O checklist completo para instalar em outro Windows ou Linux, preservar o
sequencial AFD, autenticar a Cloudflare e validar o ambiente está em
[`docs/DEPLOY.md`](docs/DEPLOY.md).

## Relatório local e screenshots

Com `MONITOR_ENABLED=true`, cada execução atualiza automaticamente:

```text
output/monitor/index.html
```

Abra esse HTML no navegador para consultar o histórico, a linha do tempo e um
screenshot de cada ação. As imagens e os dados ficam apenas na máquina local em
`output/monitor/runs`. Use `MONITOR_OUTPUT_DIR` para trocar a pasta.

`MONITOR_HISTORY_DAYS=3` mantém as execuções e screenshots dos últimos três dias
e apaga automaticamente os dados mais antigos. Essa limpeza nunca remove os
arquivos `output/AFD*.txt`.

Para reconstruir o HTML sem executar o ERP:

```powershell
rpa-ponto report
```

## Publicar o relatório na Cloudflare

O relatório completo, incluindo os screenshots, pode ser publicado no Cloudflare
Pages com login. A validação ocorre na Cloudflare e usa `PONTO_USERNAME` e
`PONTO_PASSWORD` como secrets; as credenciais não são incluídas no HTML. Instale
o Wrangler e autentique esta máquina uma vez:

```powershell
npm install
npx.cmd wrangler login
npx.cmd wrangler pages project create rpa-ponto-monitor --production-branch main
```

Esse comando de criação é necessário somente na primeira configuração da conta.
O projeto `rpa-ponto-monitor` já foi criado; em outra máquina, execute apenas
`npm ci` e `wrangler login`. Depois, configure o `.env`:

```dotenv
CLOUDFLARE_PAGES_ENABLED=true
CLOUDFLARE_PAGES_PROJECT=rpa-ponto-monitor
CLOUDFLARE_PAGES_BRANCH=main
```

A partir daí, `rpa-ponto run` publica `output/monitor` automaticamente ao final,
tanto em execuções concluídas quanto nas falhas capturadas. Para publicar somente
o relatório que já existe, sem executar o ERP:

```powershell
rpa-ponto publish
```

Antes de cada publicação, o comando sincroniza `PONTO_USERNAME`,
`PONTO_PASSWORD` e, quando preenchido, `CONTROL_AGENT_TOKEN` como secrets
criptografados do projeto Pages. A tela de login
oferece um card para instalação como aplicativo (PWA); ele não aparece no painel
de execuções depois da autenticação.

No Linux, use `npx wrangler` no lugar de `npx.cmd wrangler`. Para uma execução
sem login interativo, defina `CLOUDFLARE_ACCOUNT_ID` e `CLOUDFLARE_API_TOKEN` no
ambiente do processo, usando um token com permissão para editar o Pages.

## Executar e agendar pelo painel

O `index.html` autenticado possui o botão **Executar agora** e aceita vários
agendamentos, cada um com seu horário e dias da semana. Os horários usam
`America/Sao_Paulo`. O Pages grava a fila no D1; o Lightsail consulta a fila a
cada minuto, portanto nenhuma porta de entrada precisa ser aberta no servidor.

O banco `rpa-ponto-control` desta instalação já foi criado, migrado e seu ID está
no `wrangler.jsonc`. O servidor não precisa recriá-lo nem aplicar a migração
inicial.

Somente ao instalar em outra conta Cloudflare, crie o banco com
`npx wrangler d1 create rpa-ponto-control`, atualize o `database_id` e execute
`npx wrangler d1 migrations apply rpa-ponto-control --remote`. Gere um segredo
exclusivo no Lightsail e guarde-o somente no `.env`:

```bash
openssl rand -hex 32
sudo -u rpa-ponto -H nano /opt/rpa-ponto/.env
```

```dotenv
CONTROL_API_URL=https://rpa-ponto-monitor.pages.dev
CONTROL_AGENT_TOKEN=cole_aqui_o_valor_gerado
```

Depois publique para sincronizar o secret e instale as unidades:

```bash
cd /opt/rpa-ponto
sudo -u rpa-ponto -H .venv/bin/rpa-ponto publish
sudo cp deploy/systemd/rpa-ponto.service /etc/systemd/system/
sudo cp deploy/systemd/rpa-ponto-control.service /etc/systemd/system/
sudo cp deploy/systemd/rpa-ponto-control.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl disable --now rpa-ponto.timer
sudo systemctl enable --now rpa-ponto-control.timer
systemctl list-timers rpa-ponto-control.timer
```

O timer antigo de horário fixo deve permanecer desativado quando o controle pelo
painel estiver ativo. O arquivo de trava compartilhado impede que uma execução
manual do serviço e o agente iniciem dois fluxos simultâneos.
