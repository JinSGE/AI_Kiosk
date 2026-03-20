import os
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
from models.rag_models import Document

class DocumentLoader:
    """다양한 소스에서 문서 로딩"""
    
    @staticmethod
    def load_from_directory(directory_path: str, file_extension: str = ".txt") -> List[Document]:
        """디렉토리에서 문서 로드"""
        documents = []
        
        for file_path in Path(directory_path).glob(f"*{file_extension}"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            doc = Document(
                id=str(file_path),
                content=content,
                metadata={"source": str(file_path)}
            )
            documents.append(doc)
        
        return documents
    
    @staticmethod
    def load_from_json(json_path: str, content_key: str = "content") -> List[Document]:
        """JSON 파일에서 문서 로드"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        documents = []
        for i, item in enumerate(data):
            doc = Document(
                id=str(i),
                content=item.get(content_key, ""),
                metadata={k: v for k, v in item.items() if k != content_key}
            )
            documents.append(doc)
        
        return documents
