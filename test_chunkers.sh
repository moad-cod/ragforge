#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TEST_EMAIL="${TEST_EMAIL:-ragforge-test-$(date +%s)@example.com}"
TEST_PASSWORD="${TEST_PASSWORD:-TestPass123}"
DEFAULT_PDF_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/Rapport_de_stage_bac+3.pdf"
TEST_FILE_PATH="${TEST_FILE_PATH:-$DEFAULT_PDF_PATH}"
TEST_URL="${TEST_URL:-https://example.com}"
LLM_PROVIDER="${LLM_PROVIDER:-gemini}"
LLM_MODEL="${LLM_MODEL:-}"
RUN_LLM_TESTS="${RUN_LLM_TESTS:-1}"
RUN_URL_TEST="${RUN_URL_TEST:-0}"
RUN_GDRIVE_TEST="${RUN_GDRIVE_TEST:-0}"
RUN_MULTIMODAL_TEST="${RUN_MULTIMODAL_TEST:-1}"
RUN_ACCOUNT_DELETE_TEST="${RUN_ACCOUNT_DELETE_TEST:-0}"
GDRIVE_FILE_ID="${GDRIVE_FILE_ID:-}"
GDRIVE_ACCESS_TOKEN="${GDRIVE_ACCESS_TOKEN:-}"
MULTIMODAL_PDF_PATH="${MULTIMODAL_PDF_PATH:-$TEST_FILE_PATH}"

TMP_DIR="$(mktemp -d)"
TOKEN=""
PROJECT_ID=""
DOC_IDS=()

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

info() {
  printf '\n==> %s\n' "$1"
}

json_get() {
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get(sys.argv[1], ""))' "$1"
}

json_len() {
  python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'
}

chunker_ids_for_text_ingest() {
  python3 -c '
import json, sys
chunkers = json.load(sys.stdin)
ids = [c["id"] for c in chunkers if not c.get("requires_multimodal")]
print(" ".join(ids))
'
}

validate_chunker_metadata() {
  python3 -c '
import json, sys
chunkers = json.load(sys.stdin)
required = {
    "id", "name", "tier", "status", "is_beta", "short_description",
    "long_description", "best_for", "not_recommended_for", "speed_level",
    "quality_level", "cost_level", "requires_llm", "requires_nltk",
    "requires_embedding_model", "requires_multimodal", "default",
}
ids = [c.get("id") for c in chunkers]
expected = ["fixed_size", "paragraph", "sentence", "semantic", "hierarchical", "late_chunking", "proposition", "multimodal"]
if ids != expected:
    raise SystemExit(f"Unexpected chunker IDs: {ids}")
for chunker in chunkers:
    missing = required - set(chunker)
    extra_private = {"callable_path", "callable", "internal"} & set(chunker)
    chunker_id = chunker.get("id")
    if missing:
        raise SystemExit(f"{chunker_id} missing metadata fields: {sorted(missing)}")
    if extra_private:
        raise SystemExit(f"{chunker_id} exposed private fields: {sorted(extra_private)}")
defaults = [c["id"] for c in chunkers if c["default"]]
if defaults != ["paragraph"]:
    raise SystemExit(f"Expected paragraph as only default, got {defaults}")
if next(c for c in chunkers if c["id"] == "proposition")["status"] != "beta":
    raise SystemExit("Expected proposition to be beta")
if next(c for c in chunkers if c["id"] == "multimodal")["status"] != "experimental":
    raise SystemExit("Expected multimodal to be experimental")
print("Chunker metadata OK:", ", ".join(ids))
'
}

api() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local output="$TMP_DIR/response.json"
  local status
  local auth_args=()
  if [[ -n "$TOKEN" ]]; then
    auth_args=(-H "Authorization: Bearer $TOKEN")
  fi

  if [[ -n "$body" ]]; then
    status="$(curl -sS -o "$output" -w '%{http_code}' -X "$method" "$BASE_URL$path" \
      -H "Content-Type: application/json" \
      "${auth_args[@]}" \
      -d "$body")"
  else
    status="$(curl -sS -o "$output" -w '%{http_code}' -X "$method" "$BASE_URL$path" \
      "${auth_args[@]}")"
  fi

  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "Request failed: $method $path -> HTTP $status"
    python3 -m json.tool "$output" 2>/dev/null || cat "$output"
    return 1
  fi
  cat "$output"
}

api_allow_failure() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local output="$TMP_DIR/response.json"
  local status
  local auth_args=()
  local body_args=()
  if [[ -n "$TOKEN" ]]; then
    auth_args=(-H "Authorization: Bearer $TOKEN")
  fi
  if [[ -n "$body" ]]; then
    body_args=(-d "$body")
  fi

  status="$(curl -sS -o "$output" -w '%{http_code}' -X "$method" "$BASE_URL$path" \
    -H "Content-Type: application/json" \
    "${auth_args[@]}" \
    "${body_args[@]}")"
  echo "$status"
  cat "$output"
}

expect_http_error() {
  local expected_status="$1"
  local method="$2"
  local path="$3"
  local body="${4:-}"
  local output="$TMP_DIR/expected-error.json"
  local status
  local auth_args=()
  local body_args=()
  if [[ -n "$TOKEN" ]]; then
    auth_args=(-H "Authorization: Bearer $TOKEN")
  fi
  if [[ -n "$body" ]]; then
    body_args=(-d "$body")
  fi

  status="$(curl -sS -o "$output" -w '%{http_code}' -X "$method" "$BASE_URL$path" \
    -H "Content-Type: application/json" \
    "${auth_args[@]}" \
    "${body_args[@]}")"

  if [[ "$status" != "$expected_status" ]]; then
    echo "Expected HTTP $expected_status but got HTTP $status for $method $path"
    python3 -m json.tool "$output" 2>/dev/null || cat "$output"
    return 1
  fi
  cat "$output"
}

expect_upload_error() {
  local expected_status="$1"
  local path="$2"
  local project_id="$3"
  local chunker="$4"
  local output="$TMP_DIR/expected-upload-error.json"
  local status

  status="$(curl -sS -o "$output" -w '%{http_code}' -X POST "$BASE_URL/ingest/file" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$path" \
    -F "project_id=$project_id" \
    -F "chunker=$chunker")"

  if [[ "$status" != "$expected_status" ]]; then
    echo "Expected upload HTTP $expected_status but got HTTP $status for chunker=$chunker"
    python3 -m json.tool "$output" 2>/dev/null || cat "$output"
    return 1
  fi
  cat "$output"
}

upload_file() {
  local path="$1"
  local project_id="$2"
  local chunker="$3"
  local output="$TMP_DIR/upload.json"
  local status

  status="$(curl -sS -o "$output" -w '%{http_code}' -X POST "$BASE_URL/ingest/file" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$path" \
    -F "project_id=$project_id" \
    -F "chunker=$chunker")"

  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "Upload failed for chunker=$chunker -> HTTP $status"
    python3 -m json.tool "$output" 2>/dev/null || cat "$output"
    return 1
  fi
  cat "$output"
}

login() {
  local output="$TMP_DIR/login.json"
  local status
  status="$(curl -sS -o "$output" -w '%{http_code}' -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$TEST_EMAIL&password=$TEST_PASSWORD")"
  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "Login failed -> HTTP $status"
    python3 -m json.tool "$output" 2>/dev/null || cat "$output"
    return 1
  fi
  TOKEN="$(json_get access_token < "$output")"
  echo "Token acquired: ${TOKEN:0:20}..."
}

ensure_test_file() {
  if [[ -n "$TEST_FILE_PATH" && -f "$TEST_FILE_PATH" ]]; then
    echo "$TEST_FILE_PATH"
    return
  fi

  echo "Missing test PDF: $TEST_FILE_PATH" >&2
  echo "Set TEST_FILE_PATH=/path/to/Rapport_de_stage_bac+3.pdf or place Rapport_de_stage_bac+3.pdf in the project root." >&2
  return 1
}

info "Health"
echo "Base URL: $BASE_URL"
echo "Core PDF: $TEST_FILE_PATH"
echo "Optional toggles: RUN_URL_TEST=$RUN_URL_TEST RUN_GDRIVE_TEST=$RUN_GDRIVE_TEST RUN_MULTIMODAL_TEST=$RUN_MULTIMODAL_TEST RUN_LLM_TESTS=$RUN_LLM_TESTS"
echo "Enable all external features with: RUN_URL_TEST=1 RUN_GDRIVE_TEST=1 RUN_MULTIMODAL_TEST=1 RUN_LLM_TESTS=1"
api GET /health | python3 -m json.tool

info "Chunker registry: list metadata"
CHUNKERS_JSON="$TMP_DIR/chunkers.json"
api GET /chunkers > "$CHUNKERS_JSON"
python3 -m json.tool "$CHUNKERS_JSON"
validate_chunker_metadata < "$CHUNKERS_JSON"
read -r -a CHUNKERS <<< "$(chunker_ids_for_text_ingest < "$CHUNKERS_JSON")"
echo "Text ingestion chunkers from registry: ${CHUNKERS[*]}"

info "Auth: register, login, me, update"
api POST /auth/register "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}" | python3 -m json.tool
login
api GET /auth/me | python3 -m json.tool
api PATCH /auth/me "{\"email\":\"$TEST_EMAIL\"}" | python3 -m json.tool

info "Projects: create, list, get, update"
PROJECT_ID="$(api POST /projects/ '{"name":"Smoke Test Project"}' | json_get project_id)"
echo "Project ID: $PROJECT_ID"
api GET /projects/ | python3 -m json.tool
api GET "/projects/$PROJECT_ID" | python3 -m json.tool
api PATCH "/projects/$PROJECT_ID" '{"name":"Smoke Test Project Renamed"}' | python3 -m json.tool

TEST_FILE="$(ensure_test_file)"
echo "Using test PDF: $TEST_FILE"

info "File ingestion: all chunkers"
for CHUNKER in "${CHUNKERS[@]}"; do
  echo "-- chunker: $CHUNKER"
  DOC_ID="$(upload_file "$TEST_FILE" "$PROJECT_ID" "$CHUNKER" | json_get document_id)"
  DOC_IDS+=("$DOC_ID")
  echo "Document ID: $DOC_ID"
done

info "Invalid chunker validation"
expect_upload_error 400 "$TEST_FILE" "$PROJECT_ID" "xyz" | python3 -m json.tool
expect_upload_error 400 "$TEST_FILE" "$PROJECT_ID" "multimodal" | python3 -m json.tool

info "Documents: list and get"
api GET "/documents/?project_id=$PROJECT_ID" | python3 -m json.tool
FIRST_DOC_ID="${DOC_IDS[0]}"
api GET "/documents/$FIRST_DOC_ID" | python3 -m json.tool

if [[ "$RUN_LLM_TESTS" == "1" ]]; then
  info "RAG query: project query, document filter, include_context"
  MODEL_FIELD=""
  if [[ -n "$LLM_MODEL" ]]; then
    MODEL_FIELD=",\"model\":\"$LLM_MODEL\""
  fi
  QUERY_BODY="{\"question\":\"What is the main topic of Rapport de stage?\",\"project_id\":\"$PROJECT_ID\",\"provider\":\"$LLM_PROVIDER\",\"include_context\":true$MODEL_FIELD}"
  if ! api POST /rag/query "$QUERY_BODY" | python3 -m json.tool; then
    echo "LLM query failed. Check provider API key/server config, or rerun with RUN_LLM_TESTS=0."
  fi

  DOC_QUERY_BODY="{\"question\":\"Summarize Rapport de stage in a few points.\",\"project_id\":\"$PROJECT_ID\",\"document_id\":\"$FIRST_DOC_ID\",\"provider\":\"$LLM_PROVIDER\"$MODEL_FIELD}"
  if ! api POST /rag/query "$DOC_QUERY_BODY" | python3 -m json.tool; then
    echo "Document-filtered query failed. Check provider API key/server config, or rerun with RUN_LLM_TESTS=0."
  fi
else
  echo "Skipping LLM query tests. Set RUN_LLM_TESTS=1 to enable."
fi

if [[ "$RUN_URL_TEST" == "1" ]]; then
  info "URL ingestion"
  URL_BODY="{\"url\":\"$TEST_URL\",\"project_id\":\"$PROJECT_ID\",\"chunker\":\"paragraph\"}"
  if api POST /ingest/url "$URL_BODY" | python3 -m json.tool; then
    :
  else
    echo "URL ingestion failed. Check server network access or rerun with RUN_URL_TEST=0."
  fi
else
  echo "Skipping URL ingestion by default. Set RUN_URL_TEST=1 to enable."
fi

if [[ "$RUN_GDRIVE_TEST" == "1" ]]; then
  info "Google Drive ingestion"
  if [[ -z "$GDRIVE_FILE_ID" || -z "$GDRIVE_ACCESS_TOKEN" ]]; then
    echo "Skipping Google Drive: set GDRIVE_FILE_ID and GDRIVE_ACCESS_TOKEN."
  else
    GDRIVE_BODY="{\"file_id\":\"$GDRIVE_FILE_ID\",\"access_token\":\"$GDRIVE_ACCESS_TOKEN\",\"project_id\":\"$PROJECT_ID\",\"chunker\":\"paragraph\"}"
    api POST /ingest/gdrive "$GDRIVE_BODY" | python3 -m json.tool
  fi
fi

if [[ "$RUN_MULTIMODAL_TEST" == "1" ]]; then
  info "Multimodal PDF ingestion and query"
  if [[ ! -f "$MULTIMODAL_PDF_PATH" ]]; then
    echo "Skipping multimodal: set MULTIMODAL_PDF_PATH to a PDF file."
  else
    echo "Using multimodal PDF: $MULTIMODAL_PDF_PATH"
    MULTI_OUT="$TMP_DIR/multimodal.json"
    STATUS="$(curl -sS -o "$MULTI_OUT" -w '%{http_code}' -X POST "$BASE_URL/ingest/multimodal" \
      -H "Authorization: Bearer $TOKEN" \
      -F "file=@$MULTIMODAL_PDF_PATH" \
      -F "project_id=$PROJECT_ID")"
    if [[ "$STATUS" -lt 200 || "$STATUS" -ge 300 ]]; then
      echo "Multimodal ingestion failed -> HTTP $STATUS"
      python3 -m json.tool "$MULTI_OUT" 2>/dev/null || cat "$MULTI_OUT"
    else
      python3 -m json.tool "$MULTI_OUT"
      if [[ "$RUN_LLM_TESTS" == "1" ]]; then
        api POST /rag/multimodal-query "{\"question\":\"What is visible in the Rapport de stage pages?\",\"project_id\":\"$PROJECT_ID\"}" | python3 -m json.tool
      fi
    fi
  fi
fi

info "Delete one document"
api DELETE "/documents/$FIRST_DOC_ID" | python3 -m json.tool
api GET "/documents/?project_id=$PROJECT_ID" | python3 -m json.tool

info "Delete project"
api DELETE "/projects/$PROJECT_ID" | python3 -m json.tool
COUNT="$(api GET /projects/ | json_len)"
echo "Projects remaining for test user: $COUNT"

if [[ "$RUN_ACCOUNT_DELETE_TEST" == "1" ]]; then
  info "Delete account"
  api DELETE /auth/me | python3 -m json.tool
else
  echo "Skipping account deletion. Set RUN_ACCOUNT_DELETE_TEST=1 to test /auth/me DELETE."
fi

echo
echo "Backend smoke test completed."
