"""Extract red-teaming pass/fail data from promptfoo result.json files."""

import dataclasses
import json
from collections import defaultdict
from pathlib import Path

DEFAULT_PLUGIN_LABELS: dict[str, str] = {
    "custom": "Custom",
    "policy": "Policy",
    "hallucination": "Hallucination",
    "intent": "Intent",
}

DEFAULT_STRATEGY_LABELS: dict[str, str] = {
    "Composite": "Jailbreak:<br>Composite",
    "Hydra": "Jailbreak:<br>Hydra",
    "IterativeMeta": "Jailbreak:<br>Meta",
    "MischievousUser": "Mischievous<br>User",
}


@dataclasses.dataclass
class RedteamResult:
    plugins: list[str]
    strategies: list[str]
    raw: dict[tuple[str, str], tuple[int, int]]


def _parse_plugin(key_prefix: str) -> str:
    """Map the left side of a namedScores key to a canonical plugin id.

    Examples: "PolicyViolation:6ab218370cdd" -> "policy", "custom" -> "custom"
    """
    lower = key_prefix.lower()
    if lower.startswith("policyviolation"):
        return "policy"
    return lower


def _extract_single(
    path: Path,
    *,
    strategy_labels: dict[str, str] | None = None,
    plugin_labels: dict[str, str] | None = None,
    default_plugin: str | None = None,
    use_overall_pass: bool = False,
) -> RedteamResult:
    s_labels = {**DEFAULT_STRATEGY_LABELS, **(strategy_labels or {})}
    p_labels = {**DEFAULT_PLUGIN_LABELS, **(plugin_labels or {})}

    with open(path) as f:
        data = json.load(f)

    results = data["results"]["results"]

    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in results:
        grading = r.get("gradingResult", {})
        named_scores = grading.get("namedScores", {})

        if named_scores and not use_overall_pass:
            for key, score in named_scores.items():
                if "/" in key:
                    plugin_raw, strategy_raw = key.split("/", 1)
                else:
                    plugin_raw, strategy_raw = key, "Basic"
                plugin_id = _parse_plugin(plugin_raw)
                plugin = p_labels.get(plugin_id, plugin_id)
                strategy = s_labels.get(strategy_raw, strategy_raw)
                counts[(plugin, strategy)][0] += int(score)
                counts[(plugin, strategy)][1] += 1
        elif named_scores and use_overall_pass:
            # Use gradingResult.pass (incorporates human overrides) but keep
            # the plugin/strategy breakdown from namedScores keys.
            overall_pass = int(grading.get("pass", False))
            for key in named_scores:
                if "/" in key:
                    plugin_raw, strategy_raw = key.split("/", 1)
                else:
                    plugin_raw, strategy_raw = key, "Basic"
                plugin_id = _parse_plugin(plugin_raw)
                plugin = p_labels.get(plugin_id, plugin_id)
                strategy = s_labels.get(strategy_raw, strategy_raw)
                counts[(plugin, strategy)][0] += overall_pass
                counts[(plugin, strategy)][1] += 1
        elif default_plugin is not None:
            # Manual tests without namedScores — use gradingResult.pass
            plugin = default_plugin
            strategy = s_labels.get("Basic", "Basic")
            counts[(plugin, strategy)][0] += int(grading.get("pass", False))
            counts[(plugin, strategy)][1] += 1

    plugins = sorted({k[0] for k in counts})
    strategies = sorted({k[1] for k in counts})
    raw = {k: (v[0], v[1]) for k, v in counts.items()}
    return RedteamResult(plugins=plugins, strategies=strategies, raw=raw)


def extract_redteam_data(
    paths: Path | list[Path],
    *,
    strategy_labels: dict[str, str] | None = None,
    plugin_labels: dict[str, str] | None = None,
    default_plugin: str | None = None,
    use_overall_pass: bool = False,
) -> RedteamResult:
    """Extract and aggregate red-teaming data from one or more result.json files.

    Args:
        default_plugin: Plugin name to assign to results that have no
            namedScores (e.g. manually written test cases). If None,
            such results are skipped.
        use_overall_pass: When True, use gradingResult.pass for the pass count
            instead of the individual namedScore values. Useful for corrected
            result files where human overrides update gradingResult.pass but
            not namedScores.
    """
    if isinstance(paths, Path):
        return _extract_single(
            paths,
            strategy_labels=strategy_labels,
            plugin_labels=plugin_labels,
            default_plugin=default_plugin,
            use_overall_pass=use_overall_pass,
        )

    merged: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for path in paths:
        single = _extract_single(
            path,
            strategy_labels=strategy_labels,
            plugin_labels=plugin_labels,
            default_plugin=default_plugin,
            use_overall_pass=use_overall_pass,
        )
        for key, (passed, total) in single.raw.items():
            merged[key][0] += passed
            merged[key][1] += total

    plugins = sorted({k[0] for k in merged})
    strategies = sorted({k[1] for k in merged})
    raw = {k: (v[0], v[1]) for k, v in merged.items()}
    return RedteamResult(plugins=plugins, strategies=strategies, raw=raw)
