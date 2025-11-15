import os
import re
from typing import List, Dict, Any, Optional
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from tqdm import tqdm

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

import nltk
from nltk.tokenize import sent_tokenize
nltk.download("punkt")
nltk.download("punkt_tab")

# -------------------- ENV VARIABLES --------------------
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
API_BASE_URL = os.getenv("DOCUMENTS_API_URL", "http://web:5000/api/documents")

EMBED_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
COLLECTION_NAME = "documents_rag"

# -------------------- TEXT PREPROCESSING --------------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def chunk_text(text: str, max_sentences=5) -> List[str]:
    sents = sent_tokenize(text)
    chunks = []
    for i in range(0, len(sents), max_sentences):
        chunks.append(" ".join(sents[i:i+max_sentences]))
    return chunks or [""]

# -------------------- FETCH DOCUMENTS FROM API --------------------
def fetch_documents(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    # 1️⃣ Получаем список документов с API
    params = {}
    if limit:
        params['limit'] = limit
    resp = requests.get(f"{API_BASE_URL}/", params=params)
    resp.raise_for_status()
    docs_meta = resp.json()  # [{"id":..., "name":..., "path":...}, ...]

    documents = []
    for meta in docs_meta:
        doc_id = meta["id"]
        filename = meta.get("name", "")
        path = meta.get("path", "")
        if not path:
            content = ""
        else:
            file_path = os.path.join(path, filename)

        if not os.path.exists(file_path):
            content = ""
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

        documents.append({
            "id": doc_id,
            "title": filename,
            "content": content
        })

    return documents


# -------------------- Qdrant RAG Index --------------------
class QdrantRAG:
    def __init__(self):
        self.model = SentenceTransformer(EMBED_MODEL)
        self.dim = self.model.get_sentence_embedding_dimension()
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)

    def init_collection(self):
        colls = self.client.get_collections().collections
        if any(c.name == COLLECTION_NAME for c in colls):
            return
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE)
        )

    def build(self, docs: List[Dict[str, Any]]):
        self.init_collection()
        all_points = []
        idx = 1
        for doc in tqdm(docs, desc="Embedding documents"):
            text = clean_text(doc.get("content", ""))
            chunks = chunk_text(text)
            embeddings = self.model.encode(chunks, convert_to_numpy=True)
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                meta = {
                    "doc_id": doc["id"],
                    "chunk": i,
                    "text": chunk,
                    "title": doc.get("title", "")
                }
                all_points.append(PointStruct(id=idx, vector=emb.tolist(), payload=meta))
                idx += 1
        self.client.upsert(collection_name=COLLECTION_NAME, points=all_points)

    def search(self, query: str, top_k=5):
        q_emb = self.model.encode(query).tolist()
        results = self.client.search(collection_name=COLLECTION_NAME, query_vector=q_emb, limit=top_k)
        return results


# -------------------- FASTAPI MICROSERVICE --------------------
class BuildRequest(BaseModel):
    limit: Optional[int] = None

class QueryRequest(BaseModel):
    question: str

app = FastAPI(title="RAG Qdrant Service")

@app.post("/build")
def build_index(req: BuildRequest):
    docs = fetch_documents(limit=req.limit)
    rag = QdrantRAG()
    rag.build(docs)
    return {"status": "ok", "docs_processed": len(docs)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
