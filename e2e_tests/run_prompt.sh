#!/bin/bash
set -e

DAEMON_OPTIONS="--mock --host 127.0.0.1 --port 9874"
CLIENT_OPTIONS="--host 127.0.0.1 --port 9874"

PYTHON_EXEC=../../../python/.venv/bin/python
DAEMON_EXEC="$PYTHON_EXEC ../../../rust-copartner-daemon.py"
CLIENT_EXEC="$PYTHON_EXEC ../../../rust-copartner-client.py"

for scene in prompt/*; do
  echo "🧪 Running E2E prompt test: $scene"
  cd $scene

  # Create actual directory from original
  # The actual directory is processed by the daemon
  rm -rf actual
  cp -r original actual

  # Check if prompt.md exists
  if [[ ! -f prompt.md ]]; then
    echo "❌ No prompt.md file found in $scene"
    cd ../..
    exit 1
  fi

  # Read the prompt from prompt.md
  PROMPT=$(cat prompt.md)
  echo "💭 Using prompt: $PROMPT"

  # Run daemon in background
  $DAEMON_EXEC actual $DAEMON_OPTIONS &
  DAEMON_PID=$!

  sleep 1

  # Run client with prompt mode and auto-accept
  echo "y" | $CLIENT_EXEC --prompt "$PROMPT" $CLIENT_OPTIONS || {
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
    echo "Diff between actual and expected:"
    diff -r actual expect || true
    cd ../..
    exit 1
  fi

  # Clean up
  rm -rf actual

  cd ..
done

echo "🎉 All E2E prompt tests passed!"