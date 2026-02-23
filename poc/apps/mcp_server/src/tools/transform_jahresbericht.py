from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

SENDER_COLUMNS = [
    "SRF 1",
    "SRF zwei",
    "SRF info",
    "RTS 1",
    "RSI LA 1",
    "Andere Sender",
]

DROP_COLUMNS = ["SRG SSR Total", "SRF Total", "Restliche SRG SSR"]

DESCRIPTOR_COLUMNS = [
    "Zeitschienen",
    "Facts",
    "Aktivitäten",
    "Zielgruppe",
    "Region",
    "Jahr",
    "Zeitintervall",
]

SENDER_GROUP_MAP: dict[str, list[str]] = {
    "SRF 1": ["SRG SSR Total", "SRF Total"],
    "SRF zwei": ["SRG SSR Total", "SRF Total"],
    "SRF info": ["SRG SSR Total", "SRF Total"],
    "RTS 1": ["SRG SSR Total", "Restliche SRG SSR"],
    "RSI LA 1": ["SRG SSR Total", "Restliche SRG SSR"],
    "Andere Sender": [],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize Jahresbericht SRF/SSR sender columns for analytics-friendly storage."
    )
    parser.add_argument(
        "--input",
        default="apps/mcp_server/data/Jahresbericht21_SRF-DS.csv",
        help="Input CSV path.",
    )
    parser.add_argument(
        "--output",
        default="apps/mcp_server/data/Jahresbericht21_SRF-DS.normalized.parquet",
        help="Output Parquet path.",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Optional secondary CSV export path.",
    )
    parser.add_argument(
        "--drop-na-values",
        action="store_true",
        help="Drop rows where the melted sender value is missing.",
    )
    return parser.parse_args()


def _validate_required_columns(df: pd.DataFrame) -> None:
    required_columns = set(SENDER_COLUMNS + DROP_COLUMNS + DESCRIPTOR_COLUMNS)
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        missing_display = ", ".join(missing_columns)
        raise ValueError(f"Input CSV is missing required columns: {missing_display}")


def _build_sender_groups(sender: str) -> list[str]:
    return list(SENDER_GROUP_MAP.get(sender, []))


def transform(df: pd.DataFrame, drop_na_values: bool = False) -> pd.DataFrame:
    _validate_required_columns(df)

    id_vars = [column for column in df.columns if column not in set(SENDER_COLUMNS + DROP_COLUMNS)]

    transformed = pd.melt(
        df,
        id_vars=id_vars,
        value_vars=SENDER_COLUMNS,
        var_name="Sender",
        value_name="Wert",
    )

    transformed["Wert"] = pd.to_numeric(transformed["Wert"], errors="coerce")

    if drop_na_values:
        transformed = transformed.dropna(subset=["Wert"])

    transformed["Sendergruppen"] = transformed["Sender"].map(_build_sender_groups)

    expected_rows = len(df) * len(SENDER_COLUMNS)
    if drop_na_values:
        if len(transformed) > expected_rows:
            raise ValueError(
                f"Unexpected row count after transformation: {len(transformed)} > {expected_rows}"
            )
    elif len(transformed) != expected_rows:
        raise ValueError(
            f"Unexpected row count after transformation: {len(transformed)} != {expected_rows}"
        )

    sender_values = sorted(transformed["Sender"].dropna().unique().tolist())
    expected_senders = sorted(SENDER_COLUMNS)
    if sender_values != expected_senders:
        raise ValueError(
            "Unexpected sender values after transformation: "
            f"{sender_values} != {expected_senders}"
        )

    list_mask = transformed["Sendergruppen"].map(lambda value: isinstance(value, list))
    if not bool(list_mask.all()):
        raise ValueError("Sendergruppen contains non-list values.")

    preferred_order = DESCRIPTOR_COLUMNS + ["Sender", "Wert", "Sendergruppen"]
    available_order = [column for column in preferred_order if column in transformed.columns]
    remaining_columns = [column for column in transformed.columns if column not in available_order]
    transformed = transformed[available_order + remaining_columns]

    return transformed


def _write_output(
    transformed: pd.DataFrame,
    parquet_output_path: Path,
    csv_output_path: Path | None,
) -> None:
    parquet_output_path.parent.mkdir(parents=True, exist_ok=True)
    transformed.to_parquet(parquet_output_path, index=False)

    if csv_output_path is not None:
        csv_output_path.parent.mkdir(parents=True, exist_ok=True)
        csv_df = transformed.copy()
        csv_df["Sendergruppen_json"] = csv_df["Sendergruppen"].map(
            lambda values: json.dumps(values, ensure_ascii=False)
        )
        csv_df = csv_df.drop(columns=["Sendergruppen"])
        csv_df.to_csv(csv_output_path, index=False)


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_csv_path = Path(args.output_csv) if args.output_csv else None

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    transformed = transform(df, drop_na_values=args.drop_na_values)

    _write_output(transformed, output_path, output_csv_path)

    print(f"Input rows: {len(df)}")
    print(f"Output rows: {len(transformed)}")
    print(f"Parquet output: {output_path}")
    if output_csv_path is not None:
        print(f"CSV output: {output_csv_path}")


if __name__ == "__main__":
    main()
