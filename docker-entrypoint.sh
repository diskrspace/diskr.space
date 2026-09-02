#!/bin/sh
set -eu

python -m db.bootstrap
exec "$@"
