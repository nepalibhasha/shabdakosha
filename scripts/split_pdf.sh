#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 -i INPUT.pdf -o OUTPUT_DIR [-c CHUNK_SIZE] [-p PREFIX]"
  echo "Requires pdfseparate and pdfunite from poppler."
}

INPUT=""
OUTPUT=""
CHUNK_SIZE=2
PREFIX="kosha"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i|--input) INPUT="$2"; shift 2 ;;
    -o|--output) OUTPUT="$2"; shift 2 ;;
    -c|--chunk-size) CHUNK_SIZE="$2"; shift 2 ;;
    -p|--prefix) PREFIX="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$INPUT" || -z "$OUTPUT" ]]; then
  usage
  exit 1
fi

if ! command -v pdfinfo >/dev/null || ! command -v pdfseparate >/dev/null || ! command -v pdfunite >/dev/null; then
  echo "Missing poppler tools: install pdfinfo, pdfseparate, and pdfunite." >&2
  exit 1
fi

mkdir -p "$OUTPUT"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

pages="$(pdfinfo "$INPUT" | awk '/^Pages:/ {print $2}')"
pdfseparate "$INPUT" "$TMPDIR/page_%04d.pdf"

start=1
while [[ "$start" -le "$pages" ]]; do
  end=$((start + CHUNK_SIZE - 1))
  if [[ "$end" -gt "$pages" ]]; then
    end="$pages"
  fi
  bucket=$(( ((start - 1) / 100 + 1) * 100 ))
  outdir="$OUTPUT/$bucket"
  mkdir -p "$outdir"
  output_file="$outdir/${PREFIX}_$(printf '%04d' "$start")_$(printf '%04d' "$end").pdf"
  inputs=()
  for page in $(seq "$start" "$end"); do
    inputs+=("$TMPDIR/page_$(printf '%04d' "$page").pdf")
  done
  pdfunite "${inputs[@]}" "$output_file"
  start=$((end + 1))
done

echo "Wrote PDF chunks to $OUTPUT"
