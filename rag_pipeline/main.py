import os
import re
import tempfile
from typing import List, Dict, Any, Optional, Set

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tqdm import tqdm

from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

# Document parsing libs
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
import pdfplumber
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
from PIL import Image

# NLTK sentence tokenization
import nltk
from nltk.tokenize import sent_tokenize

nltk.download("punkt")
nltk.download("punkt_tab")

# -------------------- ENV VARIABLES --------------------
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
API_BASE_URL = os.getenv("DOCUMENTS_API_URL", "http://web:5000/api/documents")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents_rag")
PDF_POPPLER_PATH = os.getenv("PDF_POPPLER_PATH", None)  # optional path for poppler (pdf2image)
OCR_LANGS = os.getenv("OCR_LANGS", "ru")  # e.g. "ru", "en", "multilingual"

# OCR init (PaddleOCR)
ocr = PaddleOCR(use_angle_cls=True, lang=OCR_LANGS)

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

# -------------------- FILE READERS --------------------
IMAGE_EXTS = {"png", "jpg", "jpeg", "tiff", "bmp", "gif", "webp"}
TEXT_EXTS = {"txt", "md", "csv", "log", "json"}
HTML_EXTS = {"html", "htm"}
DOCX_EXTS = {"docx"}
PDF_EXTS = {"pdf"}

def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def read_html(path: str) -> str:
    raw = read_text_file(path)
    soup = BeautifulSoup(raw, "html.parser")
    return soup.get_text(separator="\n")

def read_docx(path: str) -> str:
    doc = DocxDocument(path)
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n".join(paragraphs)

def ocr_image_path(path: str) -> str:
    res = ocr.ocr(path, cls=True)
    lines = []
    # PaddleOCR returns list of results for each detected line/box
    for page in res:
        for box, (txt, conf) in page:
            lines.append(txt)
    return "\n".join(lines)

def read_pdf(path: str) -> str:
    # Try text extraction first
    text_pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_pages.append(page_text)
    except Exception as e:
        print("pdfplumber error:", e)

    extracted = "\n".join(text_pages).strip()
    if extracted:
        return extracted

    # If no text extracted, convert pages to images and OCR them
    try:
        images = convert_from_path(path, dpi=200, poppler_path=PDF_POPPLER_PATH)
    except Exception as e:
        print("pdf->image conversion error:", e)
        images = []

    ocr_texts = []
    for img in images:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp.name, format="PNG")
            try:
                txt = ocr_image_path(tmp.name)
                ocr_texts.append(txt)
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
    return "\n".join(ocr_texts)

def read_file_auto(path: str) -> str:
    ext = (path.split(".")[-1] or "").lower()
    if ext in TEXT_EXTS:
        return read_text_file(path)
    if ext in HTML_EXTS:
        return read_html(path)
    if ext in DOCX_EXTS:
        return read_docx(path)
    if ext in PDF_EXTS:
        return read_pdf(path)
    if ext in IMAGE_EXTS:
        return ocr_image_path(path)
    # fallback: try text read
    try:
        return read_text_file(path)
    except Exception:
        return ""

# -------------------- FETCH DOCUMENTS FROM API --------------------
def fetch_documents(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Ожидается, что API возвращает список метаданных:
    [{"id": 1, "name": "file.pdf", "path": "/data/documents"}, ...]
    Если поле "url" присутствует — файл будет скачан и распознан.
    """
    params = {}
    if limit:
        params["limit"] = limit
    resp = requests.get(f"{API_BASE_URL}/", params=params, timeout=30)
    resp.raise_for_status()
    docs_meta = resp.json()

    documents = []
    for meta in docs_meta:
        doc_id = meta.get("id")
        filename = meta.get("name", "")
        path = meta.get("path", "")
        url = meta.get("url", "")

        content = ""
        if url:
            # download remote file to temp
            try:
                r = requests.get(url, stream=True, timeout=30)
                r.raise_for_status()
                suffix = os.path.splitext(filename)[1] or ".bin"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    for chunk in r.iter_content(chunk_size=8192):
                        tmp.write(chunk)
                    tmp_path = tmp.name
                try:
                    content = read_file_auto(tmp_path)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
            except Exception as e:
                print(f"Failed download {url}: {e}")
                content = ""
        else:
            if not path:
                file_path = filename
            else:
                file_path = os.path.join(path, filename)
            if os.path.exists(file_path):
                content = read_file_auto(file_path)
            else:
                print(f"File not found: {file_path}")
                content = ""

        documents.append({"id": doc_id, "title": filename, "content": content})
    return documents

# -------------------- Qdrant RAG (с инкрементальной индексацией) --------------------
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

    def get_indexed_doc_ids(self) -> Set[Any]:
        """
        Получаем множество doc_id, которые уже есть в коллекции.
        Используем scroll(), учитывая что он возвращает (points, next_page_offset).
        """
        indexed: Set[Any] = set()
        try:
            offset = None
            while True:
                points, next_page = self.client.scroll(
                    collection_name=COLLECTION_NAME,
                    limit=1000,
                    with_payload=True,
                    offset=offset
                )
                for p in points:
                    payload = p.payload or {}
                    if "doc_id" in payload:
                        indexed.add(payload["doc_id"])

                if next_page is None:
                    break
                offset = next_page

        except Exception as e:
            print("get_indexed_doc_ids error:", e)

        return indexed

    def build(self, docs: List[Dict[str, Any]], reindex_existing: bool = False):
        """
        reindex_existing: если True — переиндексировать документы, даже если их doc_id уже есть.
        Если False — индексируем только новые doc_id.
        """
        self.init_collection()

        indexed_ids = self.get_indexed_doc_ids()
        print(f"📌 Indexed documents in Qdrant: {len(indexed_ids)}")

        # count existing vectors чтобы продолжить id
        try:
            cnt = self.client.count(collection_name=COLLECTION_NAME).count
        except Exception:
            cnt = 0
        next_id = int(cnt) + 1

        all_points: List[PointStruct] = []

        for doc in tqdm(docs, desc="Embedding documents"):
            doc_id = doc.get("id")
            if doc_id is None:
                # если нет id — всё равно индексируем (используем title + filename), но лучше иметь id
                print("Document without id, will index (not recommended).")
            else:
                if (doc_id in indexed_ids) and (not reindex_existing):
                    print(f"⏩ Document {doc_id} already indexed. Skipping.")
                    continue

            text = clean_text(doc.get("content", ""))
            if not text:
                print(f"⚠ Document {doc_id} has no text. Skipping.")
                continue

            chunks = chunk_text(text)
            # encode batched
            embeddings = self.model.encode(chunks, convert_to_numpy=True)

            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                meta = {
                    "doc_id": doc_id,
                    "chunk": i,
                    "text": chunk,
                    "title": doc.get("title", "")
                }
                all_points.append(PointStruct(id=next_id, vector=emb.tolist(), payload=meta))
                next_id += 1

        if all_points:
            # upsert все новые точки
            self.client.upsert(collection_name=COLLECTION_NAME, points=all_points)
            print(f"✅ Added {len(all_points)} new chunks")
        else:
            print("⚠ No new documents to index")

    def search(self, query: str, top_k=5):
        q_emb = self.model.encode(query).tolist()
        results = self.client.search(collection_name=COLLECTION_NAME, query_vector=q_emb, limit=top_k)
        return results

# -------------------- FASTAPI --------------------
class BuildRequest(BaseModel):
    limit: Optional[int] = None
    reindex_existing: Optional[bool] = False  # если true — переиндексировать все (force)

class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

app = FastAPI(title="RAG Qdrant Service with PaddleOCR (incremental)")

@app.post("/build")
def build_index(req: BuildRequest):
    try:
        docs = fetch_documents(limit=req.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed fetch_documents: {e}")
    rag = QdrantRAG()
    rag.build(docs, reindex_existing=bool(req.reindex_existing))
    return {"status": "ok", "docs_processed": len(docs)}

@app.post("/search")
def search_index(req: QueryRequest):
    rag = QdrantRAG()
    results = rag.search(req.question, top_k=req.top_k)
    out = []
    for r in results:
        payload = r.payload or {}
        out.append({
            "id": r.id,
            "score": float(r.score) if hasattr(r, "score") else None,
            "payload": payload
        })
    return {"query": req.question, "results": out}

@app.get("/indexed_ids")
def indexed_ids():
    rag = QdrantRAG()
    ids = list(rag.get_indexed_doc_ids())
    return {"indexed_doc_ids": ids, "count": len(ids)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)