#!/bin/bash

EMAIL="mouad@gmail.com"
PASSWORD="123"
PDF_PATH="/home/snow/Documents/Projects/RAGForge/Rapport_de_stage_bac+3.pdf"
BASE_URL="http://localhost:8000"

# ── Login (OAuth2 form-encoded, field is "username" not "email") ──
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$EMAIL&password=$PASSWORD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token acquired: ${TOKEN:0:20}..."

CHUNKERS=("fixed_size" "sentence" "proposition" "hierarchical" "late_chunking" "semantic")

for CHUNKER in "${CHUNKERS[@]}"; do
  echo ""
  echo "=========================================="
  echo "Testing chunker: $CHUNKER"
  echo "=========================================="

  # Create project — response key is "project_id"
  PROJECT_ID=$(curl -s -X POST "$BASE_URL/projects/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$CHUNKER\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['project_id'])")

  echo "Project ID ($CHUNKER): $PROJECT_ID"

  # Ingest PDF
  DOC_ID=$(curl -s -X POST "$BASE_URL/ingest/file" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$PDF_PATH" \
    -F "project_id=$PROJECT_ID" \
    -F "chunker=$CHUNKER" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['document_id'])")

  echo "Document ID: $DOC_ID"

  echo "--- Query result ($CHUNKER) ---"
  curl -s -X POST "$BASE_URL/rag/query" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"question\": \"what is the essential of this document?\",
      \"project_id\": \"$PROJECT_ID\",
      \"provider\": \"gemini\",
      \"model\": \"gemini-2.5-flash\"
    }" | python3 -m json.tool

done

echo ""
echo "All chunkers tested."

