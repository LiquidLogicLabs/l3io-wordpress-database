#!/usr/bin/env bash
# Start ENGINE on a free loopback port and run the full pytest suite against it.
# Serialized by make's flock; unique container names avoid PID-reuse clashes under act.
set -euo pipefail

: "${ENGINE:?set ENGINE}"
UV="${UV:-uv}"
port="${TEST_PORT:-}"
if [ -z "$port" ]; then
  port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
fi
name="l3io-test-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:12])')"
docker run -d --rm --name "$name" -e MYSQL_ROOT_PASSWORD=root -e MARIADB_ROOT_PASSWORD=root \
  -p "127.0.0.1:${port}:3306" "$ENGINE" >/dev/null
trap 'docker rm -f -v "'"$name"'" >/dev/null 2>&1' EXIT
trap 'exit 130' INT TERM
export DB_HOST=127.0.0.1 DB_PORT="$port" DB_ADMIN_USER=root DB_ADMIN_PASSWORD=root
for _ in $(seq 1 90); do
  if $UV run --no-sync python -c "import os, pymysql; pymysql.connect(host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']), user='root', password='root').close()" 2>/dev/null; then
    break
  fi
  sleep 2
done
$UV run --no-sync python -c "import os, pymysql; pymysql.connect(host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']), user='root', password='root').close()" >/dev/null
cov_xml="${COVERAGE_XML:-}"
[ -n "$cov_xml" ] || cov_xml=/tmp/l3io-coverage.xml
$UV run --no-sync pytest -q \
  --cov=l3io.wp.database --cov-report=term-missing \
  --cov-report=xml:"$cov_xml"
