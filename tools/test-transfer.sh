#!/usr/bin/env bash
# Export/import tests against ENGINE using that image's own client tools.
# Serialized by make's flock; unique names and an ephemeral port under act.
set -euo pipefail

: "${ENGINE:?set ENGINE}"
: "${CURDIR:?}"
UV="${UV:-uv}"
BINDER_WHEEL_DIR="${BINDER_WHEEL_DIR:?}"
BINDER_VERSION="${BINDER_VERSION:?}"
BINDER_WHEEL_URL="${BINDER_WHEEL_URL:?}"

mkdir -p "$BINDER_WHEEL_DIR"
wheel=$(ls "$BINDER_WHEEL_DIR"/l3io_age_passphrase-${BINDER_VERSION}-*.whl 2>/dev/null | head -1 || true)
if [ -z "$wheel" ]; then
  echo "fetching l3io-age-passphrase ${BINDER_VERSION} wheel for transfer container"
  curl -fsSL -o "$BINDER_WHEEL_DIR/$(basename "$BINDER_WHEEL_URL")" "$BINDER_WHEEL_URL"
  wheel=$(ls "$BINDER_WHEEL_DIR"/l3io_age_passphrase-${BINDER_VERSION}-*.whl | head -1)
fi
base=$(basename "$wheel")
port="${TRANSFER_PORT:-}"
if [ -z "$port" ]; then
  port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
fi
id=$(python3 -c 'import uuid; print(uuid.uuid4().hex[:12])')
name="l3io-transfer-${id}"
docker run -d --rm --name "$name" -e MYSQL_ROOT_PASSWORD=root -e MARIADB_ROOT_PASSWORD=root \
  -p "127.0.0.1:${port}:3306" "$ENGINE" >/dev/null
trap 'docker rm -f "'"$name"'" "'"$name"'-tests" >/dev/null 2>&1' EXIT
trap 'exit 130' INT TERM
docker run --rm --name "${name}-tests" --network host -v "${CURDIR}:/repo:ro" \
  -v "$wheel:/wheels/$base:ro" -e L3IO_AGE_PASSPHRASE_WHEEL=/wheels/$base \
  -e L3IO_ENGINE="$ENGINE" -e L3IO_TRANSFER_CONTAINER=1 \
  -e DB_HOST=127.0.0.1 -e DB_PORT="$port" -e DB_ADMIN_USER=root -e DB_ADMIN_PASSWORD=root \
  --entrypoint bash "$ENGINE" /repo/tools/transfer-tests.sh &
wait $!
