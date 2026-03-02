from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.expression import TableClause, column, table

from mcp_server.contracts.models import Aggregate, QueryTemplateModel, SortDirection
from mcp_server.contracts.policy_models import PolicyModel


@dataclass(frozen=True)
class QueryPlan:
    statement: Select[tuple[object, ...]]


def build_runtime_table(policy: PolicyModel) -> TableClause:
    columns = (
        set(policy.filterable)
        | set(policy.groupable)
        | set(policy.sortable)
        | set(policy.aggregates)
    )
    if "Wert" not in columns:
        columns.add("Wert")
    return table("jahresbericht", *[column(name) for name in sorted(columns)])


def _aggregate_expression(
    aggregate: Aggregate, metric_column: ColumnElement[object]
) -> ColumnElement[object]:
    if aggregate is Aggregate.SUM:
        return func.sum(metric_column)
    if aggregate is Aggregate.AVG:
        return func.avg(metric_column)
    if aggregate is Aggregate.MIN:
        return func.min(metric_column)
    if aggregate is Aggregate.MAX:
        return func.max(metric_column)
    return func.count(metric_column)


def build_query_plan(template: QueryTemplateModel, table_model: TableClause) -> QueryPlan:
    group_columns = [table_model.c[column_name] for column_name in template.group_by]

    metric_expressions: list[ColumnElement[object]] = []
    alias_map: dict[str, ColumnElement[object]] = {}
    for metric in template.metrics:
        metric_column = table_model.c[metric.column]
        aggregate_expression = _aggregate_expression(metric.aggregate, metric_column).label(
            metric.alias
        )
        metric_expressions.append(aggregate_expression)
        alias_map[metric.alias] = aggregate_expression

    statement: Select[tuple[object, ...]] = select(*group_columns, *metric_expressions)

    filter_expressions: list[ColumnElement[bool]] = []
    for filter_item in template.filters:
        model_column = table_model.c[filter_item.column]
        if filter_item.op.value == "eq":
            filter_expressions.append(model_column == filter_item.value)
        elif filter_item.op.value == "in":
            if isinstance(filter_item.value, list):
                filter_expressions.append(model_column.in_(filter_item.value))
        elif filter_item.op.value == "gte":
            filter_expressions.append(model_column >= filter_item.value)
        elif filter_item.op.value == "lte":
            filter_expressions.append(model_column <= filter_item.value)

    if filter_expressions:
        statement = statement.where(and_(*filter_expressions))

    if group_columns:
        statement = statement.group_by(*group_columns)

    for sort_item in template.sort:
        sortable_expression = alias_map.get(sort_item.column)
        if sortable_expression is None:
            sortable_expression = table_model.c[sort_item.column]
        if sort_item.direction is SortDirection.ASC:
            statement = statement.order_by(asc(sortable_expression))
        else:
            statement = statement.order_by(desc(sortable_expression))

    statement = statement.limit(template.limit)
    return QueryPlan(statement=statement)
