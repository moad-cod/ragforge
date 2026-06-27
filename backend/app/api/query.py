from fastapi import APIRouter
from pydantic import BaseModel
from app.services.embedder import embed_query
from app.services.retriever import search
from groq import Groq
from app.core.config import settings

router = APIRouter()
groq = Groq(api_key=settings.GROQ_API_KEY)

class QueryRequest(BaseModel):
    question: str

@router.post("/query")
def query(request: QueryRequest):
    query_embedding = embed_query(request.question)
    contexts = search(query_embedding, top_k=5)

    context_text = "\n\n---\n\n".join(contexts)
    prompt = f"""Answer the question using ONLY the context below.
If the answer isn't in the context, say "I don't know based on the provided documents."

Context:
{context_text}

Question: {request.question}"""

    response = groq.chat.completions.create(
        model="llama-3.3-70b-versatile",  
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )

    return {
        "question": request.question,
        "answer": response.choices[0].message.content,
        "retrieved_chunks": contexts,
    }