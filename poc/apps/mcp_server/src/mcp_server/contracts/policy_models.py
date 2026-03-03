from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mcp_server.contracts.models import Aggregate, Operator


class LimitsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_limit: int = Field(ge=1)
    max_limit: int = Field(ge=1)


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    dataset: str
    filterable: dict[str, list[Operator]]
    groupable: list[str]
    sortable: list[str]
    aggregates: dict[str, list[Aggregate]]
    limits: LimitsModel
