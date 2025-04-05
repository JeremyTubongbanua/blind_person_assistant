#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Usage: $0 command [arguments]"
    echo "Example: $0 ls -la"
    exit 1
fi

cmd="$@"

echo "Executing: $cmd"
echo "----------------------------------------"

start_time=$(date +%s%N)

eval "$cmd"
cmd_exit_code=$?

end_time=$(date +%s%N)

elapsed_ns=$((end_time - start_time))

seconds=$((elapsed_ns / 1000000000))
milliseconds=$(((elapsed_ns % 1000000000) / 1000000))

echo "----------------------------------------"
echo "Command completed with exit code: $cmd_exit_code"
echo "Execution time: ${seconds}.${milliseconds} seconds"
