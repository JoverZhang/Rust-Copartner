#!/bin/bash
set -e

for scene in e2e_tests/*; do
  echo "Running $scene"
  cd $scene
  ./run.sh
  cd ..
done
