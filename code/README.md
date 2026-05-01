# Support Triage Agent (Baseline)

A deterministic, terminal-based baseline agent for HackerRank Orchestrate.

## What it does

- Reads tickets from `support_tickets/support_tickets.csv`
- Retrieves a best-match support document from the local `data/` corpus
- Classifies request type and product area
- Escalates sensitive/unsupported issues
- Writes predictions to `support_tickets/output.csv`

## Run

```bash
python3 code/main.py \
  --input support_tickets/support_tickets.csv \
  --output support_tickets/output.csv \
  --data data
```

## Notes

- Uses local corpus only (no network calls).
- Deterministic heuristics for reproducible results.
- Extendable: replace retrieval/classification with embeddings/LLM while preserving I/O contract.
