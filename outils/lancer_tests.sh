#!/bin/bash
# Lance tous les tests (depuis n'importe ou). Resume : /tmp/tests_resume.log (ECHEC ... puis FINI)
cd "$(dirname "$0")/.."
: > /tmp/tests_resume.log
for t in tests/test_*.py; do timeout 600 python3 $t > /tmp/t_$(basename $t .py).log 2>&1 || echo "ECHEC $t" >> /tmp/tests_resume.log; done
echo FINI >> /tmp/tests_resume.log
