from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class MessageSchema(BaseModel):
    role: str
    content: str
class SessionSchema(BaseModel):
    id: str
    title: str
    messages: List[MessageSchema] = []
