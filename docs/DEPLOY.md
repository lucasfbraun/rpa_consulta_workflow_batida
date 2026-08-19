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

O teste final é executado dentro de `/opt/rpa-ponto`, já com o usuário do
serviço. Se uma instalação feita com uma versão anterior terminar somente nessa
etapa com `PermissionError` apontando para a pasta do usuário que fez o clone,
os componentes já estarão instalados. Valide novamente a partir da pasta certa:

```bash
cd /opt/rpa-ponto
sudo -u rpa-ponto -H .venv/bin/python -m pytest
```

Com os testes aprovados, prossiga para a configuração do `.env`; não é
necessário reinstalar o sistema.

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
ERP_LOCALE=pt-BR

RPA_HEADLESS=true
MONITOR_ENABLED=true
MONITOR_HISTORY_DAYS=3

CLOUDFLARE_PAGES_ENABLED=true
CLOUDFLARE_PAGES_PROJECT=rpa-ponto-monitor
CLOUDFLARE_PAGES_BRANCH=main
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
```

Use `RPA_HEADLESS=false` somente quando precisar enxergar o navegador para testar
ou diagnosticar o fluxo. Em produção, `true` permite executar apenas pelo terminal
ou por um agendador.

Mantenha `ERP_LOCALE=pt-BR`. O contexto do Chromium passa esse idioma ao ERP e
evita que uma instalação Linux em inglês altere os nomes dos campos e botões
usados pela automação.

O `.env` contém credenciais, está ignorado pelo Git e não deve ser publicado.
Consulte `.env.example` para todas as opções disponíveis.

`MONITOR_HISTORY_DAYS=3` mantém no relatório todas as execuções e screenshots dos
últimos três dias. A limpeza dos dados mais antigos acontece automaticamente e
não remove os arquivos `output/AFD*.txt`.

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
7. Para o primeiro teste, deixe **Client IP Address Filtering** sem restrição. O
   Lightsail pode acessar a API por IPv6 mesmo quando possui um IPv4 estático;
   permitir somente o IPv4 causa o erro Cloudflare `9109`. Se a política exigir
   filtro por origem, confirme depois todos os endereços de saída estáveis e
   permita IPv4 em `/32` e IPv6 em `/128`. Ao migrar, atualize ambos.
8. Selecione **Continue to summary > Create Token**.
9. Copie o token assim que ele for exibido e grave somente no `.env`:

```dotenv
CLOUDFLARE_API_TOKEN=cole_o_token_aqui
```

Não use a Global API Key, não adicione permissões de zona e não grave o token
no Git, em comandos do terminal ou em capturas de tela. Mantenha o `.env` com
permissão `600`, como definido na etapa de instalação.

### Gravar as credenciais no servidor

No PowerShell do computador administrativo, conecte-se usando a chave e o IP
estático correspondentes à instância:

```powershell
ssh -i "C:\caminho\LightsailDefaultKey-regiao.pem" ubuntu@IP_ESTATICO
```

No servidor, abra o arquivo como o usuário do serviço. Não tente lê-lo como
`ubuntu`: a permissão `600` deve impedir esse acesso.

```bash
sudo -u rpa-ponto -H nano /opt/rpa-ponto/.env
```

Preencha as linhas existentes, sem aspas e sem criar chaves duplicadas:

```dotenv
CLOUDFLARE_PAGES_ENABLED=true
CLOUDFLARE_PAGES_PROJECT=rpa-ponto-monitor
CLOUDFLARE_PAGES_BRANCH=main
CLOUDFLARE_ACCOUNT_ID=cole_o_account_id
CLOUDFLARE_API_TOKEN=cole_o_token
```

No Nano, use `Ctrl+O`, Enter e `Ctrl+X`. Nunca cole o conteúdo completo do
`.env` em tickets, chats ou logs.

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
são alternativas; não é necessário usar ambas. Em um serviço systemd sem
navegador, use o token.

Valide as credenciais e publique o relatório existente sem executar o ERP:

```bash
cd /opt/rpa-ponto
sudo -u rpa-ponto -H .venv/bin/rpa-ponto publish
```

O comando deve imprimir `Relatório online` e a URL da implantação. Se retornar
`In a non-interactive environment`, `CLOUDFLARE_API_TOKEN` está ausente ou vazio
no `.env`. Se retornar erro de autorização, confira o Account ID, a permissão
**Cloudflare Pages: Edit**, o escopo da conta, o filtro de IP e se o token foi
copiado por inteiro.

Antes do deploy, `rpa-ponto publish` sincroniza `PONTO_USERNAME`,
`PONTO_PASSWORD` e, se configurado, `CONTROL_AGENT_TOKEN` como secrets
criptografados do projeto Pages. Esses valores não
são gravados no HTML, no manifest ou no JavaScript entregue ao navegador. A
publicação inclui a Pages Function que valida o login, o cookie de sessão assinado
e os arquivos da PWA. O card **Instalar monitor** fica na própria tela de login,
antes da autenticação, e não aparece no painel de execuções. O botão usa a
instalação nativa do navegador ou orienta a adicionar o aplicativo à tela inicial.

O erro `Cannot use the access token from location ... [code: 9109]` significa que
o token foi reconhecido, mas o endereço de saída do servidor não está autorizado
pelo filtro de IP. Edite o token no painel e remova temporariamente **Client IP
Address Filtering**. Em Lightsail com IPv6, liberar somente o IPv4 estático não é
suficiente. Depois de salvar a política, o valor do token no `.env` só precisa ser
alterado se a Cloudflare emitir um novo token.

Se a edição deixar uma regra incompleta como `Is not in` com valor vazio e exibir
`Insira endereços IP válidos`, cancele a edição e crie um novo token com as mesmas
permissões, sem interagir com a seção de filtragem de IP. Troque o token no `.env`,
valide a publicação e somente depois revogue o token antigo.

Cada chave deve aparecer somente uma vez no `.env`. Um bloco duplicado no final
do arquivo com `CLOUDFLARE_API_TOKEN=` vazio pode sobrescrever o bloco preenchido
e produzir o mesmo erro de ambiente não interativo. Verifique sem mostrar os
segredos:

```bash
sudo awk -F= '
/^CLOUDFLARE_(PAGES_ENABLED|PAGES_PROJECT|PAGES_BRANCH|ACCOUNT_ID|API_TOKEN)=/ {
  valor=substr($0,index($0,"=")+1)
  print NR, $1 ": " (length(valor) ? "configurado" : "VAZIO")
}' /opt/rpa-ponto/.env
```

Se alguma chave aparecer duas vezes, edite o arquivo com
`sudo -u rpa-ponto -H nano /opt/rpa-ponto/.env`, remova o bloco duplicado e
mantenha uma única ocorrência preenchida de cada chave.

Depois da primeira publicação, abra
<https://rpa-ponto-monitor.pages.dev/> e confirme que o screenshot mais recente
é exibido. Com `CLOUDFLARE_PAGES_ENABLED=true`, as execuções futuras publicarão
automaticamente tanto resultados concluídos quanto falhas capturadas.

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

## 8. Agendamento fixo legado no Linux com systemd

O repositório inclui um serviço e um timer em `deploy/systemd`. O modelo executa
o RPA diariamente às 06:00 no fuso horário configurado no Linux. Confira o fuso:

Esta opção permanece documentada para instalações antigas. Não a mantenha ativa
junto com o controle do painel descrito na seção 12.

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
sudo systemctl restart rpa-ponto.timer
```

Confira a configuração persistente e o próximo disparo:

```bash
timedatectl
systemctl list-timers rpa-ponto.timer
sudo systemctl status rpa-ponto.timer --no-pager
```

No Lightsail configurado para São Paulo, a validação deve mostrar:

- `Time zone: America/Sao_Paulo (-03, -0300)`;
- `Loaded: ... enabled`, confirmando que o timer volta após reinicializações;
- `Active: active (waiting)`;
- próximo `Trigger` às `06:00:00 -03`.

Se aparecer `06:00:00 UTC`, ajuste o fuso com `timedatectl set-timezone` e
reinicie o timer. Se aparecer `disabled`, execute novamente
`sudo systemctl enable --now rpa-ponto.timer`.

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

Pare o timer, entre na pasta do projeto, atualize o código e valide antes de
reativá-lo. O `cd` precisa acontecer antes do `pytest`: o usuário `rpa-ponto` não
tem permissão para usar `/home/ubuntu` como diretório de trabalho.

```bash
sudo systemctl stop rpa-ponto.timer rpa-ponto-control.timer
sudo systemctl status rpa-ponto.service --no-pager

cd /opt/rpa-ponto
sudo -u rpa-ponto -H git status --short
sudo -u rpa-ponto -H git pull --ff-only
sudo -u rpa-ponto -H .venv/bin/python -m pip install -e "/opt/rpa-ponto[dev]"
sudo -u rpa-ponto -H npm ci --prefix /opt/rpa-ponto
sudo .venv/bin/python -m playwright install-deps chromium
sudo -u rpa-ponto -H .venv/bin/python -m playwright install chromium
sudo -u rpa-ponto -H .venv/bin/python -m pytest tests
sudo cp deploy/systemd/rpa-ponto.service /etc/systemd/system/
sudo cp deploy/systemd/rpa-ponto-control.service /etc/systemd/system/
sudo cp deploy/systemd/rpa-ponto-control.timer /etc/systemd/system/
sudo -u rpa-ponto -H .venv/bin/rpa-ponto publish

sudo systemctl daemon-reload
sudo systemctl disable rpa-ponto.timer
sudo systemctl enable --now rpa-ponto-control.timer
sudo systemctl restart rpa-ponto-control.timer
systemctl list-timers rpa-ponto-control.timer
sudo systemctl status rpa-ponto-control.timer --no-pager
```

O `output` e o `.env` são ignorados pelo Git e permanecem na máquina durante o
`pull`. Mesmo assim, confirme que nenhum RPA está rodando antes de atualizar. Se
`git status --short` listar alterações em arquivos versionados, não use
`git reset`; examine-as com `sudo -u rpa-ponto -H git diff` antes de continuar.
O `publish` atualiza imediatamente o login, a PWA e o relatório, sem precisar
executar uma nova importação no ERP.

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
- a tela de login do Pages mostrar o card da PWA e o painel autenticado não
  repeti-lo;
- `systemctl status rpa-ponto-control.timer` mostrar `enabled` e `active (waiting)`;
- o painel permitir criar, pausar e excluir mais de um agendamento;
- o botão **Executar agora** gerar um pedido que o agente coleta em até um minuto.

## 11. Diagnóstico e migração para outro Linux

### Atualização pelo usuário correto

O instalador mantém dois locais distintos: o clone inicial usado para executar o
instalador e a aplicação definitiva em `/opt/rpa-ponto`. O systemd usa somente a
aplicação em `/opt/rpa-ponto`, que pertence ao usuário `rpa-ponto`.

Não execute `git pull` diretamente como `ubuntu` dentro de `/opt/rpa-ponto`:

```bash
ubuntu@servidor:/opt/rpa-ponto$ git pull
fatal: detected dubious ownership in repository at '/opt/rpa-ponto'
```

Esse erro é esperado porque o repositório pertence ao usuário de serviço
`rpa-ponto`. Não execute `git config --global --add safe.directory`, não use
`sudo git pull` como `root` e não mude o proprietário da pasta. Depois de enviar
o commit ao GitHub, faça a atualização e confira o commit recebido com:

```bash
sudo -u rpa-ponto -H git -C /opt/rpa-ponto pull --ff-only
sudo -u rpa-ponto -H git -C /opt/rpa-ponto log -1 --oneline
```

Quando a atualização também alterar código ou dependências, continue pelo fluxo
completo da seção 9, que reinstala o pacote, executa os testes, publica o painel e
reativa o timer.

### Servidor sem interface gráfica

Estas configurações devem existir no `.env` do Linux:

```dotenv
RPA_HEADLESS=true
ERP_LOCALE=pt-BR
```

`RPA_HEADLESS=false` tenta abrir uma janela e falha com `Missing X server or
$DISPLAY`. `ERP_LOCALE=pt-BR` evita que o ERP troque campos como `Usuário` por
`User` devido ao idioma padrão do Linux.

### Consultar a execução que falhou

Consulte primeiro o journal, sem executar novamente e gerar outro AFD:

```bash
sudo systemctl status rpa-ponto.service --no-pager --full
sudo journalctl -u rpa-ponto.service --since "10 minutes ago" --no-pager
```

O journal informa o ID da execução. Use esse ID para listar as etapas e imagens:

```bash
sudo grep -E '"name"|"status"|"message"' \
  /opt/rpa-ponto/output/monitor/runs/ID_DA_EXECUCAO/run.json
sudo find /opt/rpa-ponto/output/monitor/runs/ID_DA_EXECUCAO \
  -maxdepth 1 -type f -name '*.png' -printf '%f\n'
```

Se a Cloudflare ainda não estiver configurada, copie um screenshot para o
usuário administrativo:

```bash
sudo install -o ubuntu -g ubuntu -m 600 \
  /opt/rpa-ponto/output/monitor/runs/ID_DA_EXECUCAO/ARQUIVO.png \
  /home/ubuntu/falha-rpa.png
```

Saia do SSH com `exit` e, no PowerShell local, faça o download. Substitua os
valores em maiúsculas; não escreva literalmente `IP_ESTATICO`:

```powershell
scp -i "C:\caminho\LightsailDefaultKey-regiao.pem" `
  ubuntu@IP_ESTATICO:/home/ubuntu/falha-rpa.png `
  "$env:USERPROFILE\Downloads\falha-rpa.png"
```

Digitar o caminho da imagem como se fosse um comando retorna `Permission denied`;
um servidor headless não abre a imagem no terminal. Baixe-a por SCP ou consulte-a
no relatório do Pages.

### Checklist de uma nova migração

1. associe um novo IP estático e libere-o no firewall do ERP;
2. execute o instalador automático da seção 3;
3. transfira o AFD mais recente para preservar o sequencial;
4. configure `RPA_HEADLESS=true` e `ERP_LOCALE=pt-BR`;
5. crie um novo token da Cloudflare ou atualize o filtro de IP do token existente;
6. preencha o novo `.env`, que nunca é transferido pelo Git;
7. configure `MONITOR_HISTORY_DAYS=3` e teste a publicação com
   `rpa-ponto publish`, confirmando o login e o card da PWA;
8. execute uma importação controlada e confira journal, screenshots e logout;
9. configure `America/Sao_Paulo`, ative `rpa-ponto-control.timer` e confirme
   `enabled`, `active (waiting)` e a consulta do painel a cada minuto;
10. somente então desative definitivamente a máquina antiga.

## 12. Controle e múltiplos agendamentos pelo painel

O painel autenticado permite iniciar o fluxo e cadastrar quantos agendamentos
forem necessários. Cada agendamento pode ser editado, pausado, reativado ou
excluído. A fila e os horários ficam no Cloudflare D1; o agente no
Lightsail consulta o painel a cada minuto. Todos os horários são interpretados em
`America/Sao_Paulo`.

O banco desta instalação já foi criado, recebeu a migração inicial e está
vinculado no `wrangler.jsonc`. Não o recrie no Lightsail.

Ao usar outra conta Cloudflare, execute `npx wrangler d1 create
rpa-ponto-control`, atualize o `database_id` retornado e aplique as migrações com
`npx wrangler d1 migrations apply rpa-ponto-control --remote`. No `.env` do
Lightsail, configure:

```dotenv
CONTROL_API_URL=https://rpa-ponto-monitor.pages.dev
CONTROL_AGENT_TOKEN=um_segredo_aleatorio_de_64_caracteres
```

Gere o token sem publicá-lo em logs ou no Git:

```bash
openssl rand -hex 32
sudo -u rpa-ponto -H nano /opt/rpa-ponto/.env
```

Publique o painel e troque o agendador fixo pelo agente:

```bash
cd /opt/rpa-ponto
sudo -u rpa-ponto -H .venv/bin/rpa-ponto publish
sudo cp deploy/systemd/rpa-ponto.service /etc/systemd/system/
sudo cp deploy/systemd/rpa-ponto-control.service /etc/systemd/system/
sudo cp deploy/systemd/rpa-ponto-control.timer /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/rpa-ponto.service /etc/systemd/system/rpa-ponto-control.service /etc/systemd/system/rpa-ponto-control.timer
sudo systemctl daemon-reload
sudo systemctl disable --now rpa-ponto.timer
sudo systemctl enable --now rpa-ponto-control.timer
systemctl list-timers rpa-ponto-control.timer
sudo journalctl -u rpa-ponto-control.service -n 50 --no-pager
```

Antes de ativar esse timer em produção, o teste manual de
`sudo systemctl start rpa-ponto.service` deve terminar com sucesso. Enquanto o
ERP estiver retornando timeout, deixe `rpa-ponto-control.timer` desativado para
que pedidos do painel não gerem novas tentativas automaticamente.
