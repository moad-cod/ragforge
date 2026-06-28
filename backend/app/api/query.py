from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services.embedder import embed_query
from app.services.retriever import search
from app.core.config import settings
from openai import OpenAI

router = APIRouter()

gemini = OpenAI(
    api_key=settings.GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

class QueryRequest(BaseModel):
    question: str

@router.post("/query")
def query(
    request: QueryRequest,
    version: str = Query(default="v1", enum=["v1", "v2", "v3"]),
):
    collection = f"ragforge_{version}"
    query_embedding = embed_query(request.question)
    contexts = search(query_embedding, top_k=5, collection=collection)

    context_text = "\n\n---\n\n".join(contexts)
    prompt = f"""Answer the question using ONLY the context below.
If the answer isn't in the context, say "I don't know based on the provided documents."

Context:
{context_text}

Question: {request.question}"""

    response = gemini.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=1024,
    )

    return {
        "question": request.question,
        "version": version,
        "answer": response.choices[0].message.content,
        "retrieved_chunks": contexts,
    }