from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer
from api.db.base import Base

class Document(Base):
    '''Tracks uploaded documents metadata.'''
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(primary_key=True) # UUID
    filename: Mapped[str] = mapped_column(String)
    file_type: Mapped[str] = mapped_column(String)
    qdrant_collection_id: Mapped[str] = mapped_column(String)
