#!/bin/bash
set -e

DAEMON_OPTIONS="--mock --host 127.0.0.1 --port 9875"
CLIENT_OPTIONS="--host 127.0.0.1 --port 9875"

PYTHON_EXEC=../../../python/.venv/bin/python
FIX_DIFF_SCRIPT="$PYTHON_EXEC ../../../utils/fix_diff.py"

DAEMON_EXEC="$PYTHON_EXEC ../../../rust-copartner-daemon.py"
CLIENT_EXEC="$PYTHON_EXEC ../../../rust-copartner-client.py"

for scene in interactive/*; do
  echo "🧪 Running E2E test: $scene"
  cd $scene

  # Create actual directory from original
  # The actual directory is processed by the daemon
  rm -rf actual
  cp -r original actual

  # Generate last_change.diff
  diff -u original edited \
    | grep -vE '^diff -u ' \
    | $FIX_DIFF_SCRIPT original edited > edited.diff

  # Run daemon in background
  $DAEMON_EXEC actual $DAEMON_OPTIONS &
  DAEMON_PID=$!

  sleep 1

  # Run client with auto-accept
  echo "y" | $CLIENT_EXEC edited.diff $CLIENT_OPTIONS || {
    echo "❌ Client failed for $scene"
    kill $DAEMON_PID 2>/dev/null || true
    cd ../..
    exit 1
  }

  # Stop daemon
  kill $DAEMON_PID 2>/dev/null || true
  wait $DAEMON_PID 2>/dev/null || true

  # Verify results by comparing actual with expected
  if diff --exclude=".*" -q actual expect >/dev/null 2>&1; then
    echo "✅ PASSED: $scene"
  else
    echo "❌ FAILED: $scene - Results don't match expected"
    echo "Diff:"
    diff actual expect || true
    cd ../..
    exit 1
  fi

  # Clean up
  rm -rf actual edited.diff

  cd ..
done

echo "🎉 All E2E tests passed!"
