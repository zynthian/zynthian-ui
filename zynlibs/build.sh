#!/bin/bash

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

scripts=(
  "zynsmf/build.sh"
  "zynseq/build.sh"
  "zynaudioplayer/build.sh"
  "zynmixer/build.sh"
  "zynclippy/build.sh"
)

overall_success=0
failed_scripts=()

for script in "${scripts[@]}"; do
  echo "Running $script..."
  "$SCRIPT_PATH/$script"
  exit_code=$?

  if [ $exit_code -ne 0 ]; then
    echo "❌ $script failed (exit code $exit_code)"
    overall_success=1
    failed_scripts+=("$script")
  else
    echo "✅ $script succeeded"
  fi

  echo
done

echo "=============================="
if [ $overall_success -eq 0 ]; then
  echo "🎉 Overall result: SUCCESS — all scripts completed successfully"
else
  echo "⚠️  Overall result: FAILURE"
  echo "Failed scripts:"
  for script in "${failed_scripts[@]}"; do
    echo "  - $script"
  done
fi
echo "=============================="

exit $overall_success
