from dataclasses import dataclass
from pydantic import BaseModel
from typing import List

class UpdateItem(BaseModel):
    item: str
    status: str
    identified_blockers: List[str]

@dataclass
class StandupUpdate(BaseModel):
    preferred_style: str
    updates: List[UpdateItem]