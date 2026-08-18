#!/usr/bin/env bash

set -Eeuo pipefail

RPA_USER="${RPA_USER:-rpa-ponto}"
RPA_INSTALL_DIR="${RPA_INSTALL_DIR:-/opt/rpa-ponto}"
RPA_REPO_URL="${RPA_REPO_URL:-https://github.com/lucasfbraun/rpa_consulta_workflow_batida.git}"
RPA_BRANCH="${RPA_BRANCH:-main}"
NODE_MAJOR="${NODE_MAJOR:-24}"

TEMP_DIR=""

cleanup() {
  if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
    rm -rf -- "$TEMP_DIR"
  fi
}

trap cleanup EXIT

log() {
  printf '\n==> %s\n' "$1"
}

fail() {
  printf '\nERRO: %s\n' "$1" >&2
  exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
  fail "execute este instalador como root: sudo bash scripts/install-linux.sh"
fi

if [[ ! -r /etc/os-release ]]; then
  fail "não foi possível identificar a distribuição Linux"
fi

# shellcheck disable=SC1091
source /etc/os-release
case "${ID:-}" in
  ubuntu|debian) ;;
  *) fail "distribuição não suportada: ${PRETTY_NAME:-desconhecida}. Use Ubuntu ou Debian" ;;
esac

if [[ ! "$RPA_USER" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  fail "RPA_USER contém caracteres inválidos"
fi

if [[ "$RPA_INSTALL_DIR" != /* ]]; then
  fail "RPA_INSTALL_DIR deve ser um caminho absoluto"
fi

if [[ ! "$RPA_INSTALL_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
  fail "RPA_INSTALL_DIR contém caracteres não suportados"
fi

case "$RPA_INSTALL_DIR" in
  /|/opt|/usr|/var|/home|/root) fail "RPA_INSTALL_DIR é amplo demais: $RPA_INSTALL_DIR" ;;
esac

log "Instalando pacotes básicos do sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git python3 python3-pip python3-venv xz-utils

PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_OK="$(python3 -c 'import sys; print("yes" if sys.version_info >= (3, 11) else "no")')"
if [[ "$PYTHON_OK" != "yes" ]]; then
  fail "Python 3.11 ou mais recente é obrigatório; esta máquina possui Python $PYTHON_VERSION. Use Ubuntu 24.04+ ou Debian 12+"
fi

install_node() {
  local machine node_arch checksum_file archive node_dir
  machine="$(uname -m)"
  case "$machine" in
    x86_64|amd64) node_arch="x64" ;;
    aarch64|arm64) node_arch="arm64" ;;
    *) fail "arquitetura não suportada pelo instalador do Node.js: $machine" ;;
  esac

  TEMP_DIR="$(mktemp -d)"
  checksum_file="$TEMP_DIR/SHASUMS256.txt"
  curl --fail --silent --show-error --location \
    "https://nodejs.org/dist/latest-v${NODE_MAJOR}.x/SHASUMS256.txt" \
    --output "$checksum_file"

  archive="$(awk -v suffix="linux-${node_arch}.tar.xz" '$2 ~ suffix "$" { print $2; exit }' "$checksum_file")"
  [[ -n "$archive" ]] || fail "não foi possível localizar o pacote Node.js para $node_arch"

  curl --fail --silent --show-error --location \
    "https://nodejs.org/dist/latest-v${NODE_MAJOR}.x/${archive}" \
    --output "$TEMP_DIR/$archive"

  (
    cd "$TEMP_DIR"
    grep "  ${archive}$" SHASUMS256.txt | sha256sum --check --status -
  ) || fail "a soma de verificação do Node.js não confere"

  install -d -m 755 /usr/local/lib/nodejs
  tar -xJf "$TEMP_DIR/$archive" -C /usr/local/lib/nodejs
  node_dir="/usr/local/lib/nodejs/${archive%.tar.xz}"
  ln -sfn "$node_dir/bin/node" /usr/local/bin/node
  ln -sfn "$node_dir/bin/npm" /usr/local/bin/npm
  ln -sfn "$node_dir/bin/npx" /usr/local/bin/npx
}

NODE_OK="no"
if command -v node >/dev/null 2>&1; then
  INSTALLED_NODE_MAJOR="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
  if [[ "$INSTALLED_NODE_MAJOR" =~ ^[0-9]+$ ]] \
    && (( INSTALLED_NODE_MAJOR >= 22 )) \
    && (( INSTALLED_NODE_MAJOR % 2 == 0 )); then
    NODE_OK="yes"
  fi
fi

if [[ "$NODE_OK" != "yes" ]]; then
  log "Instalando Node.js ${NODE_MAJOR} LTS com verificação de integridade"
  install_node
else
  log "Mantendo Node.js compatível já instalado: $(node --version)"
fi

command -v npm >/dev/null 2>&1 || fail "npm não foi encontrado após a instalação do Node.js"

log "Preparando o usuário de serviço"
if ! id "$RPA_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$RPA_USER"
fi
RPA_GROUP="$(id -gn "$RPA_USER")"
RPA_HOME="$(getent passwd "$RPA_USER" | cut -d: -f6)"
[[ -n "$RPA_HOME" ]] || fail "não foi possível identificar o diretório pessoal de $RPA_USER"
if [[ ! "$RPA_HOME" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
  fail "o diretório pessoal de $RPA_USER contém caracteres não suportados"
fi

as_rpa() {
  runuser -u "$RPA_USER" -- env \
    HOME="$RPA_HOME" \
    PATH="/usr/local/bin:/usr/bin:/bin" \
    "$@"
}

log "Preparando o código em $RPA_INSTALL_DIR"
if [[ -d "$RPA_INSTALL_DIR/.git" ]]; then
  as_rpa test -w "$RPA_INSTALL_DIR" || fail "$RPA_USER não possui escrita em $RPA_INSTALL_DIR"
  log "Repositório existente preservado; o instalador não executará git pull"
elif [[ -e "$RPA_INSTALL_DIR" ]]; then
  if [[ -n "$(find "$RPA_INSTALL_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    fail "$RPA_INSTALL_DIR já existe, não está vazio e não é um repositório Git"
  fi
  chown "$RPA_USER:$RPA_GROUP" "$RPA_INSTALL_DIR"
  as_rpa git clone --branch "$RPA_BRANCH" --single-branch "$RPA_REPO_URL" "$RPA_INSTALL_DIR"
else
  install -d -o "$RPA_USER" -g "$RPA_GROUP" -m 755 "$RPA_INSTALL_DIR"
  as_rpa git clone --branch "$RPA_BRANCH" --single-branch "$RPA_REPO_URL" "$RPA_INSTALL_DIR"
fi

[[ -f "$RPA_INSTALL_DIR/pyproject.toml" ]] || fail "pyproject.toml não encontrado em $RPA_INSTALL_DIR"
[[ -f "$RPA_INSTALL_DIR/package-lock.json" ]] || fail "package-lock.json não encontrado em $RPA_INSTALL_DIR"

log "Instalando o projeto Python e as dependências Node.js"
if [[ ! -x "$RPA_INSTALL_DIR/.venv/bin/python" ]]; then
  as_rpa python3 -m venv "$RPA_INSTALL_DIR/.venv"
fi
as_rpa "$RPA_INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
as_rpa "$RPA_INSTALL_DIR/.venv/bin/python" -m pip install -e "$RPA_INSTALL_DIR[dev]"
as_rpa npm ci --prefix "$RPA_INSTALL_DIR"

log "Instalando as bibliotecas do Chromium"
"$RPA_INSTALL_DIR/.venv/bin/python" -m playwright install-deps chromium
log "Instalando o Chromium para o usuário $RPA_USER"
as_rpa "$RPA_INSTALL_DIR/.venv/bin/python" -m playwright install chromium

log "Criando a configuração local sem sobrescrever credenciais existentes"
if [[ ! -f "$RPA_INSTALL_DIR/.env" ]]; then
  install -o "$RPA_USER" -g "$RPA_GROUP" -m 600 \
    "$RPA_INSTALL_DIR/.env.example" "$RPA_INSTALL_DIR/.env"
  ENV_CREATED="yes"
else
  chown "$RPA_USER:$RPA_GROUP" "$RPA_INSTALL_DIR/.env"
  chmod 600 "$RPA_INSTALL_DIR/.env"
  ENV_CREATED="no"
fi
install -d -o "$RPA_USER" -g "$RPA_GROUP" -m 700 "$RPA_INSTALL_DIR/output"

log "Instalando as unidades do systemd, ainda desativadas"
[[ -f "$RPA_INSTALL_DIR/deploy/systemd/rpa-ponto.service" ]] || fail "unidade systemd do serviço não encontrada"
[[ -f "$RPA_INSTALL_DIR/deploy/systemd/rpa-ponto.timer" ]] || fail "unidade systemd do timer não encontrada"
if [[ -z "$TEMP_DIR" ]]; then
  TEMP_DIR="$(mktemp -d)"
fi
sed \
  -e "s|^User=rpa-ponto$|User=$RPA_USER|" \
  -e "s|^Group=rpa-ponto$|Group=$RPA_GROUP|" \
  -e "s|^WorkingDirectory=/opt/rpa-ponto$|WorkingDirectory=$RPA_INSTALL_DIR|" \
  -e "s|^Environment=HOME=/home/rpa-ponto$|Environment=HOME=$RPA_HOME|" \
  -e "s|^ExecStart=/opt/rpa-ponto/|ExecStart=$RPA_INSTALL_DIR/|" \
  "$RPA_INSTALL_DIR/deploy/systemd/rpa-ponto.service" \
  > "$TEMP_DIR/rpa-ponto.service"
install -m 644 "$TEMP_DIR/rpa-ponto.service" /etc/systemd/system/rpa-ponto.service
install -m 644 "$RPA_INSTALL_DIR/deploy/systemd/rpa-ponto.timer" /etc/systemd/system/rpa-ponto.timer
systemd-analyze verify /etc/systemd/system/rpa-ponto.service /etc/systemd/system/rpa-ponto.timer
systemctl daemon-reload

log "Executando os testes automatizados"
as_rpa "$RPA_INSTALL_DIR/.venv/bin/python" -m pytest "$RPA_INSTALL_DIR/tests"

printf '\nInstalação concluída.\n'
printf 'Python: %s\n' "$("$RPA_INSTALL_DIR/.venv/bin/python" --version 2>&1)"
printf 'Node.js: %s\n' "$(node --version)"
printf 'npm: %s\n' "$(npm --version)"
printf 'Wrangler: %s\n' "$(as_rpa "$RPA_INSTALL_DIR/node_modules/.bin/wrangler" --version)"
printf '\nPróximos passos (a importação ainda NÃO foi executada):\n'
if [[ "$ENV_CREATED" == "yes" ]]; then
  printf '1. Preencha as credenciais: sudo -u %s -H nano %s/.env\n' "$RPA_USER" "$RPA_INSTALL_DIR"
else
  printf '1. Confira as credenciais preservadas em %s/.env\n' "$RPA_INSTALL_DIR"
fi
printf '2. Teste o fluxo: sudo systemctl start rpa-ponto.service\n'
printf '3. Confira o resultado: sudo systemctl status rpa-ponto.service\n'
printf '4. Ative o agendamento: sudo systemctl enable --now rpa-ponto.timer\n'
