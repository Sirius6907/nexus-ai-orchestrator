from fastapi import APIRouter, UploadFile, File
from api.rag.ingestion import DocumentIngestor
import os
router = APIRouter()

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    # Save file temporally
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())
        
    # Read text (assuming TXT for now)
    with open(temp_path, "r", encoding="utf-8") as f:
        text = f.read()
        
    ingestor = DocumentIngestor()
    chunks = await ingestor.ingest_document(text, collection_name="user_uploads")
    
    os.remove(temp_path)
    return {"message": f"Ingested {file.filename} into {chunks} chunks."}
