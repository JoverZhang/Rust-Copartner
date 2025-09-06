#!/bin/bash
set -e

rm -rf actual
cp -r before/ actual/

cd actual
git apply ../suggest.diff
cd ..

if diff -u expect actual | grep .; then
  echo "Failed"
  exit 1
fi

echo "Passed"
exit 0
