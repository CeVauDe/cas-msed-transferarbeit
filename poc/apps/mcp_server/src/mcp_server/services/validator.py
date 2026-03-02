from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from mcp_server.contracts.models import FilterModel, MetricModel, QueryTemplateModel
from mcp_server.contracts.policy_models import PolicyModel


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    template: QueryTemplateModel | None
    error: dict[str, object] | None


def _error(error_code: str, message: str, details: dict[str, object]) -> ValidationResult:
    return ValidationResult(
        valid=False,
        template=None,
        error={"error_code": error_code, "message": message, "details": details},
    )


def _validate_metric(metric: MetricModel, policy: PolicyModel) -> ValidationResult | None:
    allowed_aggregates = policy.aggregates.get(metric.column)
    if allowed_aggregates is None:
        return _error(
            "POLICY_VIOLATION",
            f"Metric column '{metric.column}' is not allowed.",
            {"field": "metrics.column", "column": metric.column},
        )

    if metric.aggregate not in allowed_aggregates:
        return _error(
            "POLICY_VIOLATION",
            f"Aggregate '{metric.aggregate.value}' is not allowed for column '{metric.column}'.",
            {
                "field": "metrics.aggregate",
                "column": metric.column,
                "allowed": [aggregate.value for aggregate in allowed_aggregates],
            },
        )
    return None


def _validate_filter(filter_item: FilterModel, policy: PolicyModel) -> ValidationResult | None:
    allowed_ops = policy.filterable.get(filter_item.column)
    if allowed_ops is None:
        return _error(
            "POLICY_VIOLATION",
            f"Filter column '{filter_item.column}' is not allowed.",
            {"field": "filters.column", "column": filter_item.column},
        )

    if filter_item.op not in allowed_ops:
        return _error(
            "POLICY_VIOLATION",
            f"Operator '{filter_item.op.value}' is not allowed for column '{filter_item.column}'.",
            {
                "field": "filters.op",
                "column": filter_item.column,
                "allowed": [operator.value for operator in allowed_ops],
            },
        )

    if filter_item.op.value == "in" and not isinstance(filter_item.value, list):
        return _error(
            "SCHEMA_VALIDATION_ERROR",
            "Operator 'in' requires list value.",
            {"field": "filters.value", "expected": "list"},
        )

    if (
        filter_item.op.value == "in"
        and isinstance(filter_item.value, list)
        and len(filter_item.value) == 0
    ):
        return _error(
            "SCHEMA_VALIDATION_ERROR",
            "Operator 'in' requires a non-empty list.",
            {"field": "filters.value", "expected": "non-empty-list"},
        )

    return None


def validate_template(raw_template: dict[str, object], policy: PolicyModel) -> ValidationResult:
    try:
        parsed_template = QueryTemplateModel.model_validate(raw_template)
    except ValidationError as exc:
        return ValidationResult(
            valid=False,
            template=None,
            error={
                "error_code": "SCHEMA_VALIDATION_ERROR",
                "message": "Template schema validation failed.",
                "details": {"errors": exc.errors()},
            },
        )

    resolved_limit = parsed_template.limit or policy.limits.default_limit
    if resolved_limit > policy.limits.max_limit:
        return _error(
            "POLICY_VIOLATION",
            "Requested limit exceeds maximum allowed limit.",
            {
                "field": "limit",
                "requested": resolved_limit,
                "max": policy.limits.max_limit,
            },
        )

    for metric in parsed_template.metrics:
        metric_error = _validate_metric(metric, policy)
        if metric_error is not None:
            return metric_error

    for filter_item in parsed_template.filters:
        filter_error = _validate_filter(filter_item, policy)
        if filter_error is not None:
            return filter_error

    # --- Assumption: Cross-region aggregation is not valid ---
    # Each region has a different sender set and audience base.
    # Require exactly one Region eq-filter per query.
    region_eq_filters = [
        f for f in parsed_template.filters if f.column == "Region" and f.op.value == "eq"
    ]
    if len(region_eq_filters) != 1:
        return _error(
            "POLICY_VIOLATION",
            "Exactly one 'Region' filter with operator 'eq' is required.",
            {"field": "filters", "column": "Region"},
        )

    group_violations = [name for name in parsed_template.group_by if name not in policy.groupable]
    if group_violations:
        return _error(
            "POLICY_VIOLATION",
            "One or more group_by columns are not allowed.",
            {"field": "group_by", "invalid": group_violations},
        )

    metric_aliases = {metric.alias for metric in parsed_template.metrics}
    for sort_item in parsed_template.sort:
        if sort_item.column in metric_aliases:
            continue
        if (
            sort_item.column not in policy.sortable
            and sort_item.column not in parsed_template.group_by
        ):
            return _error(
                "POLICY_VIOLATION",
                f"Sort column '{sort_item.column}' is not allowed.",
                {"field": "sort.column", "column": sort_item.column},
            )

    normalized_template = parsed_template.model_copy(update={"limit": resolved_limit})
    return ValidationResult(valid=True, template=normalized_template, error=None)
