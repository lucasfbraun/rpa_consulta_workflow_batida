# RPA de ponto para ERP

O projeto tem três etapas independentes:

1. consulta a API por HTTP Basic Auth;
2. converte a resposta para o arquivo aceito pelo ERP;
3. abre o ERP com Playwright e importa o arquivo.

A separação permite desenvolver no Windows e executar depois no Linux sem alterar
o fluxo da automação.

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
cp .env.example .env
```

O endereço configurado em `ERP_URL` é privado. A máquina Linux precisará estar na
mesma rede, VPN ou rota que alcança o ERP.

Antes de ativar o modo headless, valide uma importação com
`RPA_HEADLESS=false`. Depois, altere para `true` e execute novamente.
