#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <model-id> <input.csv> <output.csv>" >&2
  exit 2
fi

model_id=$1
input_csv=$2
output_csv=$3

if [[ ! -f "$input_csv" ]]; then
  echo "Input CSV not found: $input_csv" >&2
  exit 1
fi

awk -v model="$model_id" '
  NR == 1 { print "model," $0; next }
  { print model "," $0 }
' "$input_csv" > "$output_csv"

echo "wrote: $output_csv"
