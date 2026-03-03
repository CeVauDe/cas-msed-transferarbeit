# Changelog

## 2026-02-23

### Added
- Implemented MCP server for constrained, read-only access to transformed Jahresbericht data.
- Added strict query template contracts with `pydantic` models and exported JSON schema.
- Added central allowlist policy and glossary/catalog contracts.
- Added SQLAlchemy Core + DuckDB execution pipeline for validated templates.
- Added MCP tools: `query_data` and `get_catalog`.
- Added default/debug response shaping with global debug toggle.
- Added structured request lifecycle logging with OTel-ready fields.
- Added startup artifact checks for schema/policy/catalog/parquet.
- Added unit tests for validator, policy enforcement, planner, response builder, and server module.

### Changed
- Replaced placeholder MCP server loop with FastMCP server bootstrap and tool registration.
- Updated Docker Compose MCP server environment configuration for runtime defaults.
- Expanded PoC README with MCP tool usage, template examples, error codes, and troubleshooting.
