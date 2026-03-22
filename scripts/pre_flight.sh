#!/usr/bin/env bash
# Phase 7 pre-flight — run ONCE before first docker compose up.
# Starts Docker Qdrant, verifies local/networked Qdrant parity (FIX-14),
# and populates Docker Qdrant with KB chunks.
#
# Usage: bash scripts/pre_flight.sh
set -euo pipefail

echo "=== NeonatalGuard Phase 7 Pre-Flight ==="

# 1. Start only the Qdrant service
echo "[1/4] Starting Docker Qdrant..."
docker compose up qdrant -d
echo "Waiting for Qdrant to become healthy..."
sleep 8

# 2. FIX-14: Parity test — verify local file-based and networked Qdrant return identical results
echo "[2/4] FIX-14: Running Qdrant parity test..."
QDRANT_HOST=localhost QDRANT_PORT=6333 python tests/test_qdrant_parity.py
echo "Parity test PASSED."

# 3. Populate Docker Qdrant with KB chunks
# QDRANT_PATH="" triggers networked mode in _get_kb(); QDRANT_HOST points to Docker Qdrant.
echo "[3/4] Populating Docker Qdrant with KB chunks..."
QDRANT_PATH="" QDRANT_HOST=localhost QDRANT_PORT=6333 python scripts/write_chunks.py
echo "KB populated."

# 4. Verify chunk count
echo "[4/4] Verifying chunk count..."
python -c "
import os; os.environ['QDRANT_PATH'] = ''
os.environ['QDRANT_HOST'] = 'localhost'; os.environ['QDRANT_PORT'] = '6333'
from src.knowledge.knowledge_base import ClinicalKnowledgeBase
kb = ClinicalKnowledgeBase()
count = kb.client.count('clinical_knowledge').count
print(f'Docker Qdrant chunk count: {count}')
assert count == 34, f'Expected 34 chunks, got {count}'
print('Chunk count OK.')
"

echo ""
echo "=== Pre-flight complete. Run: docker compose up ==="
