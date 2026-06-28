import requests
import json

QUERY_URL = "http://localhost:8000/rag/query"

with open("tests/test_set.json") as f:
    test_set = json.load(f)

# Test just first question on v1
item = test_set[0]
response = requests.post(
    QUERY_URL,
    params={"version": "v1"},
    json={"question": item["question"]},
)
data = response.json()

print("QUESTION:", item["question"])
print("\nEXPECTED relevant_chunk:")
print(repr(item["relevant_chunk"]))
print("\nACTUAL retrieved chunks:")
for i, chunk in enumerate(data["retrieved_chunks"]):
    print(f"\n--- Chunk {i+1} ---")
    print(repr(chunk[:200]))