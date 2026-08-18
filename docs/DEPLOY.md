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

### Arquitetura escolhida no Amazon Lightsail

Para esta instalação, o ERP será publicado pelo firewall da empresa somente para
o IP estático da instância Lightsail. A Cloudflare participa apenas da publicação
do relatório e não é a origem das conexões destinadas ao ERP.

Ao criar a instância:

1. use a região **South America (São Paulo), `sa-east-1`**;
2. escolha Linux com Ubuntu, opção **OS Only**;
3. prefira o plano de 4 GB de RAM para dar folga ao Chromium;
4. crie e associe um **Static IP** antes de configurar o firewall;
5. no firewall do Lightsail, mantenha somente SSH liberado a partir dos IPs
   administrativos necessários. O RPA não recebe conexões HTTP da Internet.

No firewall da empresa, crie uma regra restrita:

```text
Origem: IP estático da instância Lightsail
Destino: endereço público/NAT que encaminha para o ERP
Porta: 443/TCP, ou a porta HTTPS definida para o ERP
```

Não libere todas as faixas da Cloudflare para essa finalidade. O IP padrão de
uma instância Lightsail pode mudar depois de parar e iniciar a máquina; por isso,
a regra deve usar o Static IP associado.

Na máquina Linux, `ERP_URL` precisa apontar para um endereço publicamente
roteável, preferencialmente um hostname com certificado HTTPS válido:

```dotenv
ERP_URL=https://erp.seudominio.com.br
ERP_VERIFY_TLS=true
```

`https://10.1.1.220` continua sendo um endereço privado e não deve ser usado no
Lightsail. Antes de executar o RPA, valide a conectividade a partir da instância:

```bash
curl --silent --show-error --output /dev/null \
  --write-out 'HTTP %{http_code}\n' --connect-timeout 10 \
  https://erp.seudominio.com.br
```

Respostas como `200`, `302`, `401` ou `403` comprovam que o servidor respondeu;
o código esperado depende da tela inicial do ERP. Timeout, falha de DNS ou erro
de certificado precisam ser corrigidos antes do deploy.

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

### Instalação automática (recomendada)

No Ubuntu 24.04 ou Debian 12 (ou versões mais recentes), clone o projeto em uma
pasta temporária e execute o instalador:

```bash
git clone https://github.com/lucasfbraun/rpa_consulta_workflow_batida.git ~/rpa-ponto-instalador
cd ~/rpa-ponto-instalador
sudo bash scripts/install-linux.sh
```

O script é idempotente e prepara automaticamente:

- pacotes básicos do sistema e Python 3.11 ou mais recente;
- Node.js LTS compatível, npm e as dependências travadas no `package-lock.json`;
- usuário `rpa-ponto` e projeto em `/opt/rpa-ponto`;
- ambiente virtual Python, Chromium e bibliotecas do Playwright;
- `.env` privado, sem substituir um arquivo que já exista;
- serviço e timer do systemd, inicialmente desativados;
- testes automatizados do projeto.

O instalador não preenche credenciais, não executa a importação e não ativa o
timer. Ao terminar, siga os quatro comandos exibidos por ele. Isso evita que um
servidor recém-criado acesse o ERP com configurações incompletas.

Para uma instalação existente, o código e o `.env` são preservados. O instalador
não executa `git pull`; atualize o código conforme a seção 9 e rode novamente o
script se quiser reconciliar todas as dependências.

As opções podem ser alteradas por variáveis no mesmo comando. Por exemplo:

```bash
sudo RPA_INSTALL_DIR=/opt/rpa-ponto RPA_BRANCH=main bash scripts/install-linux.sh
```

As variáveis disponíveis são `RPA_USER`, `RPA_INSTALL_DIR`, `RPA_REPO_URL`,
`RPA_BRANCH` e `NODE_MAJOR`. Os valores padrão já correspondem a este projeto.

### Instalação manual

Os comandos abaixo consideram `/opt/rpa-ponto` como pasta definitiva e criam um
usuário exclusivo para o serviço. Instale antes Git, Python, os módulos de
ambiente virtual, Node.js LTS e npm pelos meios recomendados para a distribuição.

Crie o usuário e clone o repositório:

```bash
sudo useradd --create-home --shell /bin/bash rpa-ponto
sudo install -d -o rpa-ponto -g rpa-ponto /opt/rpa-ponto
sudo -u rpa-ponto -H git clone https://github.com/lucasfbraun/rpa_consulta_workflow_batida.git /opt/rpa-ponto
```

Se o repositório for privado, configure antes uma chave de deploy ou outra
credencial de leitura para o usuário `rpa-ponto`.

Instale o projeto e as dependências reproduzíveis do Node pelo `package-lock.json`:

```bash
sudo -u rpa-ponto -H python3 -m venv /opt/rpa-ponto/.venv
sudo -u rpa-ponto -H /opt/rpa-ponto/.venv/bin/python -m pip install -e "/opt/rpa-ponto[dev]"
sudo -u rpa-ponto -H npm ci --prefix /opt/rpa-ponto
```

Instale primeiro as bibliotecas do sistema como `root` e depois o Chromium como
o mesmo usuário que executará o RPA. Isso garante que o navegador seja salvo no
diretório correto:

```bash
sudo /opt/rpa-ponto/.venv/bin/python -m playwright install-deps chromium
sudo -u rpa-ponto -H /opt/rpa-ponto/.venv/bin/python -m playwright install chromium
```

Crie o arquivo de configuração privado:

```bash
sudo -u rpa-ponto cp /opt/rpa-ponto/.env.example /opt/rpa-ponto/.env
sudo chmod 600 /opt/rpa-ponto/.env
sudo -u rpa-ponto -H nano /opt/rpa-ponto/.env
sudo -u rpa-ponto mkdir -p /opt/rpa-ponto/output
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
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
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

Depois da cópia, garanta que o arquivo pertença ao usuário do serviço:

```bash
sudo chown rpa-ponto:rpa-ponto /opt/rpa-ponto/output/AFD*.txt
```

Se não quiser copiar o arquivo, configure `AFD_INITIAL_SEQUENCE` no novo `.env`
com o número do último AFD gerado. Sem uma dessas medidas, uma instalação vazia
voltará a usar como base o sequencial definido no `.env`.

Não deixe as duas máquinas executando simultaneamente, pois cada uma controla o
sequencial apenas pelos arquivos presentes em seu próprio diretório `output`.

## 6. Autenticar a nova máquina na Cloudflare

O projeto `rpa-ponto-monitor` já existe. Não execute `pages project create` na
nova máquina.

### Obter o Account ID

1. Entre em <https://dash.cloudflare.com/> e selecione a conta que contém o
   projeto `rpa-ponto-monitor`.
2. Abra **Workers & Pages**.
3. Em **Account details**, copie o **Account ID**.
4. Grave o valor somente no `.env` da máquina Linux:

```dotenv
CLOUDFLARE_ACCOUNT_ID=cole_o_account_id_aqui
```

O Account ID identifica a conta e não é a senha ou o token.

### Criar o API Token

1. No painel da Cloudflare, abra o menu do perfil e acesse **My Profile > API
   Tokens**.
2. Selecione **Create Token**.
3. Em **Custom Token**, selecione **Get started**.
4. Use um nome descritivo, como `rpa-ponto-linux`.
5. Em **Permissions**, escolha exatamente:
   **Account > Cloudflare Pages > Edit**.
6. Em **Account Resources**, use **Include > Specific account** e selecione apenas
   a conta que contém `rpa-ponto-monitor`.
7. Selecione **Continue to summary > Create Token**.
8. Copie o token assim que ele for exibido e grave somente no `.env`:

```dotenv
CLOUDFLARE_API_TOKEN=cole_o_token_aqui
```

Não use a Global API Key, não adicione permissões de zona e não grave o token
no Git, em comandos do terminal ou em capturas de tela. Mantenha o `.env` com
permissão `600`, como definido na etapa de instalação.

### Escolher a forma de autenticação

Para uma máquina com navegador, também é possível usar o login OAuth:

```powershell
npx.cmd wrangler login
npx.cmd wrangler whoami
```

No Linux, os comandos equivalentes são:

```bash
npx wrangler login
npx wrangler whoami
```

Para um servidor sem login interativo, preencha no `.env`:

```text
CLOUDFLARE_ACCOUNT_ID=<id da conta>
CLOUDFLARE_API_TOKEN=<token restrito à conta e ao Cloudflare Pages>
```

Não grave o token no repositório. O arquivo `.env` é carregado pelo RPA e as
variáveis são herdadas pelo Wrangler. O login OAuth ou as duas variáveis acima
são alternativas; não é necessário usar ambas.

Valide as credenciais no Linux sem mostrar o token:

```bash
sudo -u rpa-ponto -H sh -c 'cd /opt/rpa-ponto && npx wrangler whoami'
```

O comando deve listar a conta esperada. Se retornar erro de autenticação,
confira o Account ID, a permissão **Cloudflare Pages: Edit**, o escopo da conta e
se o token foi copiado por inteiro.

## 7. Validação antes de colocar em produção

No Linux, execute os testes como o usuário definitivo do serviço:

```bash
cd /opt/rpa-ponto
sudo -u rpa-ponto -H .venv/bin/python -m pytest
sudo -u rpa-ponto -H .venv/bin/rpa-ponto fetch
sudo -u rpa-ponto -H .venv/bin/rpa-ponto import --file ./output/AFD_SEQUENCIAL.txt
sudo -u rpa-ponto -H .venv/bin/rpa-ponto publish
```

Substitua `AFD_SEQUENCIAL.txt` pelo nome gerado pelo primeiro comando. Depois
execute o fluxo completo:

```bash
sudo -u rpa-ponto -H .venv/bin/rpa-ponto run
```

Confira:

- o retorno do comando deve ser zero;
- somente o AFD mais recente deve permanecer em `output`;
- `output/monitor/index.html` deve mostrar a execução finalizada;
- o relatório deve aparecer em <https://rpa-ponto-monitor.pages.dev/>;
- o logout do ERP deve ter sido concluído.

## 8. Agendamento no Linux com systemd

O repositório inclui um serviço e um timer em `deploy/systemd`. O modelo executa
o RPA diariamente às 06:00 no fuso horário configurado no Linux. Confira o fuso:

```bash
timedatectl
sudo timedatectl set-timezone America/Sao_Paulo
```

Instale os arquivos:

```bash
sudo cp /opt/rpa-ponto/deploy/systemd/rpa-ponto.service /etc/systemd/system/
sudo cp /opt/rpa-ponto/deploy/systemd/rpa-ponto.timer /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/rpa-ponto.service /etc/systemd/system/rpa-ponto.timer
sudo systemctl daemon-reload
sudo systemctl enable --now rpa-ponto.timer
```

Para mudar o horário, edite `OnCalendar` em
`/etc/systemd/system/rpa-ponto.timer`. Exemplos:

```ini
# Todos os dias às 06:00
OnCalendar=*-*-* 06:00:00

# Somente de segunda a sexta às 07:30
OnCalendar=Mon..Fri *-*-* 07:30:00
```

Depois de alterar:

```bash
sudo systemctl daemon-reload
sudo systemctl restart rpa-ponto.timer
```

`Persistent=true` faz uma execução perdida acontecer quando a máquina voltar.
O systemd não inicia uma segunda instância da mesma unidade enquanto ela ainda
estiver ativa.

Confira o agendamento e faça uma execução controlada antes de depender do timer:

```bash
systemctl list-timers rpa-ponto.timer
sudo systemctl start rpa-ponto.service
sudo systemctl status rpa-ponto.service
journalctl -u rpa-ponto.service -n 200 --no-pager
```

Para acompanhar uma execução ao vivo:

```bash
journalctl -u rpa-ponto.service -f
```

Para desativar o agendamento:

```bash
sudo systemctl disable --now rpa-ponto.timer
```

Em produção, dispare execuções manuais com
`sudo systemctl start rpa-ponto.service`, evitando rodar o executável em paralelo
fora do systemd.

## 9. Atualizar uma instalação existente

Pare o timer, atualize o código e valide antes de reativá-lo:

```bash
sudo systemctl stop rpa-ponto.timer
sudo -u rpa-ponto -H git -C /opt/rpa-ponto pull --ff-only
sudo -u rpa-ponto -H /opt/rpa-ponto/.venv/bin/python -m pip install -e "/opt/rpa-ponto[dev]"
sudo -u rpa-ponto -H npm ci --prefix /opt/rpa-ponto
sudo /opt/rpa-ponto/.venv/bin/python -m playwright install-deps chromium
sudo -u rpa-ponto -H /opt/rpa-ponto/.venv/bin/python -m playwright install chromium
sudo -u rpa-ponto -H /opt/rpa-ponto/.venv/bin/python -m pytest /opt/rpa-ponto/tests
sudo systemctl daemon-reload
sudo systemctl start rpa-ponto.timer
```

O `output` e o `.env` são ignorados pelo Git e permanecem na máquina durante o
`pull`. Mesmo assim, confirme que nenhum RPA está rodando antes de atualizar.

## 10. Critérios para considerar o deploy concluído

Seguir este guia instala todos os componentes do projeto, mas a conclusão depende
de condições externas que o instalador não consegue garantir. Considere o deploy
aprovado somente quando:

- `sudo -u rpa-ponto -H /opt/rpa-ponto/.venv/bin/python -m pytest /opt/rpa-ponto/tests`
  terminar sem falhas;
- a máquina alcançar o `ERP_URL` pela rede ou VPN;
- `sudo systemctl start rpa-ponto.service` terminar com sucesso;
- o relatório mostrar importação e logout concluídos;
- <https://rpa-ponto-monitor.pages.dev/> receber a nova execução;
- `systemctl list-timers rpa-ponto.timer` mostrar o próximo horário.
