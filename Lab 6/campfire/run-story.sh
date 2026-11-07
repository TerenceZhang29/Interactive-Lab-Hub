#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv --system-site-packages .venv
fi
.venv/bin/python -m pip --disable-pip-version-check install -r requirements-pi.txt

export MQTT_USERNAME=idd
read -rsp 'Course MQTT password: ' MQTT_PASSWORD
export MQTT_PASSWORD
printf '\n'
exec .venv/bin/python publish.py story "$@"
