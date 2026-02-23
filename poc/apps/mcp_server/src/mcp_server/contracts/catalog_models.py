from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CatalogColumnModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description_de: str
    type: str
    allowed_examples: list[str] = Field(default_factory=list)
    aliases_de: list[str] = Field(default_factory=list)


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    columns: dict[str, CatalogColumnModel]
