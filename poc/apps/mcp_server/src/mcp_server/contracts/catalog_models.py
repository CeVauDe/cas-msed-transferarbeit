from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MetricDefinitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description_de: str
    unit: str


class TimeslotDurationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description_de: str
    note: str


class CatalogColumnModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description_de: str
    type: str
    allowed_values: list[str] = Field(default_factory=list)
    allowed_examples: list[str] = Field(default_factory=list)
    aliases_de: list[str] = Field(default_factory=list)


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    columns: dict[str, CatalogColumnModel]
    metrics: dict[str, MetricDefinitionModel] = Field(default_factory=dict)
    timeslot_durations: dict[str, TimeslotDurationModel] = Field(default_factory=dict)
