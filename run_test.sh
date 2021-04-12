#!/bin/bash

if [ -L ${BASH_SOURCE-$0} ]; then
  BIN=$(dirname $(readlink "${BASH_SOURCE-$0}"))
else
  BIN=$(dirname ${BASH_SOURCE-$0})
fi
BIN=$(cd "${BIN}">/dev/null; pwd)

echo ""
echo "[Run tests]"
if [ $# -eq 0 ] || [ "${1}" == "-p" ]; then
  python -m unittest discover -s ${BIN}/luna_ml $@
else
  # e.g. tests.test_executor.TestExecutor
  PYTHONPATH=${BIN}/luna_ml python -m unittest $@
fi
