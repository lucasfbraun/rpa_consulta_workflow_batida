# Instalação em outra máquina

Este guia prepara uma máquina nova para executar o fluxo completo: consultar a
API de ponto, gerar o AFD, importar no ERP, registrar screenshots e publicar o
relatório no Cloudflare Pages.

## 1. Pré-requisitos

- Python 3.11 ou mais recente;
- Node.js em uma versão LTS suportada e npm;
- acesso de rede ao endereço configurado em `ERP_URL`;
- acesso HTTPS à API de ponto e à Cloudflare;
- os arquivos deste projeto, incluindo `package-lock.json`.

O ERP usa um endereço privado. A nova máquina precisa estar na mesma rede, VPN
ou rota que permita alcançá-lo.

## 2. Instalação no Windows

Abra o PowerShell na pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
npm ci
Copy-Item .env.example .env
```

## 3. Instalação no Linux

Instale antes o Python, os módulos de ambiente virtual, Node.js LTS e npm pelos
meios recomendados para a distribuição. Depois, dentro da pasta do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m playwright install --with-deps chromium
npm ci
cp .env.example .env
```

Em um servidor Linux sem ambiente gráfico, configure `RPA_HEADLESS=true`.
Nesse modo, o Chromium roda invisível. A automação do ERP, os screenshots, o
relatório e a publicação na Cloudflare permanecem ativos.

## 4. Configuração do `.env`

Preencha pelo menos:

```dotenv
PONTO_USERNAME=
PONTO_PASSWORD=
PONTO_API_URL=https://relogio-ponto.lucasfbraun.workers.dev/api/records/afd

ERP_URL=
ERP_USERNAME=
ERP_PASSWORD=

RPA_HEADLESS=true
MONITOR_ENABLED=true
MONITOR_KEEP_RUNS=1

CLOUDFLARE_PAGES_ENABLED=true
CLOUDFLARE_PAGES_PROJECT=rpa-ponto-monitor
CLOUDFLARE_PAGES_BRANCH=main
```

Use `RPA_HEADLESS=false` somente quando precisar enxergar o navegador para testar
ou diagnosticar o fluxo. Em produção, `true` permite executar apenas pelo terminal
ou por um agendador.

O `.env` contém credenciais, está ignorado pelo Git e não deve ser publicado.
Consulte `.env.example` para todas as opções disponíveis.

## 5. Preservar o sequencial AFD

Antes de desativar a máquina antiga, copie o AFD mais recente para a pasta
`output` da nova máquina. O gerador localizará esse arquivo e usará o próximo
número.

Se não quiser copiar o arquivo, configure `AFD_INITIAL_SEQUENCE` no novo `.env`
com o número do último AFD gerado. Sem uma dessas medidas, uma instalação vazia
voltará a usar como base o sequencial definido no `.env`.

Não deixe as duas máquinas executando simultaneamente, pois cada uma controla o
sequencial apenas pelos arquivos presentes em seu próprio diretório `output`.

## 6. Autenticar a nova máquina na Cloudflare

O projeto `rpa-ponto-monitor` já existe. Não execute `pages project create` na
nova máquina. Para uma máquina com navegador:

```powershell
npx.cmd wrangler login
npx.cmd wrangler whoami
```

No Linux, os comandos equivalentes são:

```bash
npx wrangler login
npx wrangler whoami
```

Para um servidor sem login interativo, configure no ambiente do serviço:

```text
CLOUDFLARE_ACCOUNT_ID=<id da conta>
CLOUDFLARE_API_TOKEN=<token restrito à conta e ao Cloudflare Pages>
```

Não grave o token no repositório. O login OAuth ou as duas variáveis acima são
alternativas; não é necessário usar ambas.

## 7. Validação antes de colocar em produção

Teste primeiro cada parte separadamente:

```powershell
rpa-ponto fetch
rpa-ponto import --file .\output\AFD_SEQUENCIAL.txt
rpa-ponto publish
```

No Linux, troque o caminho do arquivo por
`./output/AFD_SEQUENCIAL.txt`. Depois execute o fluxo completo:

```text
rpa-ponto run
```

Confira:

- o retorno do comando deve ser zero;
- somente o AFD mais recente deve permanecer em `output`;
- `output/monitor/index.html` deve mostrar a execução finalizada;
- o relatório deve aparecer em <https://rpa-ponto-monitor.pages.dev/>;
- o logout do ERP deve ter sido concluído.

## 8. Execução recorrente

O projeto ainda não instala uma agenda automaticamente. Depois da validação,
execute `rpa-ponto run` pelo Agendador de Tarefas do Windows, `systemd timer`,
cron ou outra ferramenta de agendamento da máquina.

O processo agendado deve iniciar na pasta raiz do projeto, pois o `.env`,
`output` e `node_modules` são resolvidos a partir dela.
