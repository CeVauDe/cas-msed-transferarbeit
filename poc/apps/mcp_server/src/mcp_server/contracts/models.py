from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Operator(StrEnum):
    EQ = "eq"
    IN = "in"
    GTE = "gte"
    LTE = "lte"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class Aggregate(StrEnum):
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"


class MetricModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    aggregate: Aggregate
    alias: str = Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


class FilterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    op: Operator
    value: object


class SortModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    direction: SortDirection


class QueryTemplateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: list[MetricModel] = Field(min_length=1)
    filters: list[FilterModel] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    sort: list[SortModel] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1)
