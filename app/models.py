"""Dataclass model for one PMFBY knowledge record."""
from dataclasses import dataclass

@dataclass
class Record:
    id: int
    rule_topic: str
    rule_text: str
    og_version: str
    applies_to: str
    deadline_or_rate: str
    source_url: str

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**{field: data[field] for field in cls.__dataclass_fields__})
