import re
from pathlib import Path
from typing import NamedTuple

import pandas as pd

# ---------------------------------------------------------------------------
# Named return types
# ---------------------------------------------------------------------------


class FileMeta(NamedTuple):
    jahr: int
    region: str


class Timeslot(NamedTuple):
    zeitschiene: str
    timeslot_start: str
    timeslot_end: str
    timeslot_duration_minutes: int


# ---------------------------------------------------------------------------
# Filename metadata
# ---------------------------------------------------------------------------

# Pattern: Jahresbericht{YY}_{SRF|nonSRF}-{DS|SI|SR}_{date}_FB.xlsx
_FILENAME_RE = re.compile(r"Jahresbericht(\d{2})_(?:non)?SRF-([A-Z]+)_")

_REGION_MAP: dict[str, str] = {
    "DS": "Deutschschweiz",
    "SR": "Suisse romande",
    "SI": "Svizzera italiana",
}


def parse_filename_metadata(file_path: Path) -> FileMeta:
    m = _FILENAME_RE.search(file_path.name)
    if not m:
        raise ValueError(f"Cannot parse metadata from filename: {file_path.name}")
    region_code = m.group(2)
    region = _REGION_MAP.get(region_code, region_code)
    return FileMeta(jahr=2000 + int(m.group(1)), region=region)


# ---------------------------------------------------------------------------
# Timeslot parsing
# ---------------------------------------------------------------------------

# The broadcast day runs 02:00–26:00 (midnight = 24:00, not 00:00).
_SPECIAL_TIMESLOTS: dict[str, Timeslot] = {
    "Whole day": Timeslot("Whole day", "02:00:00", "26:00:00", 24 * 60),
    "18-23h": Timeslot("18-23h", "18:00:00", "23:00:00", 5 * 60),
}


def parse_timeslot(value: str) -> Timeslot:
    if value in _SPECIAL_TIMESLOTS:
        return _SPECIAL_TIMESLOTS[value]
    start_str, end_str = value.split(" - ", maxsplit=1)
    start_h, start_m, _ = (int(x) for x in start_str.strip().split(":"))
    end_h, end_m, _ = (int(x) for x in end_str.strip().split(":"))
    duration_minutes = (end_h * 60 + end_m) - (start_h * 60 + start_m)
    return Timeslot(value.strip(), start_str.strip(), end_str.strip(), duration_minutes)


# ---------------------------------------------------------------------------
# Kenngrössen mapping
# ---------------------------------------------------------------------------

_KENNGROESSE_MAP: dict[str, str] = {
    "Rt-T": "Rating in 1'000",
    "Rt-%": "Rating in %",
    "NRw-T": "Nettoreichweite in 1'000",
    "NRw-%": "Nettoreichweite in %",
    "MA-%": "Marktanteil in %",
    # Raw Excel values (with unit suffix)
    "SD Ø [Sekunden]": "durchschnittliche Sehdauer in Sekunden",
    "VD Ø [Sekunden]": "durchschnittliche Verweildauer in Sekunden",
    # Stripped forms (after whitespace/suffix cleanup)
    "SD Ø": "durchschnittliche Sehdauer in Sekunden",
    "VD Ø": "durchschnittliche Verweildauer in Sekunden",
}


# ---------------------------------------------------------------------------
# Single-file transformation
# ---------------------------------------------------------------------------


# Raw Excel layout (102 rows × 65 or 100 cols):
#   row 0:    title string – dropped
#   row 1:    L1 header ("Overnight+7") – sparse, forward-filled across columns
#   row 2:    metric names (Rt-T, Rt-%, NRw-T, NRw-%, MA-%, SD Ø, VD Ø)
#             – sparse, forward-filled; each label spans its station group
#   row 3:    station names (SRG SSR Total, SRF Total, …)
#   rows 4–99:  96 × 15-min timeslot data rows (02:00–26:00)
#   row 100:  "Whole day" summary (02:00–26:00, 1440 min)
#   row 101:  "18-23h" summary (18:00–23:00, 300 min)
#
# col 0 (Zielgruppen / audience segment) is always "Personen 3+" → dropped.
def load_and_transform(file_path: Path) -> pd.DataFrame:
    """Return a long-format DataFrame for one Jahresbericht Excel file.

    Columns: Jahr, Region, Zeitschiene, timeslot_start, timeslot_end,
             timeslot_duration_minutes, Kenngrösse, Sender, Wert
    """
    meta = parse_filename_metadata(file_path)

    df_raw = pd.read_excel(file_path, header=None)
    assert df_raw.shape[0] == 102, f"Expected 102 rows, got {df_raw.shape[0]}"

    # Drop the title row; afterwards: row 0 = L1-header, row 1 = L2-header,
    # row 2 = station names, rows 3–100 = data.
    df = df_raw.drop(index=0).reset_index(drop=True)

    # Each header label appears only in the first column of its group; ffill
    # propagates it rightward across the group's columns.
    df.iloc[0] = df.iloc[0].ffill()
    df.iloc[1] = df.iloc[1].ffill()

    # Save header rows before dropping col 0: the metric_map / station_map
    # lookups below need the original (pre-drop) column indices.
    header_rows = df.iloc[0:3].copy()

    # Drop col 0 (Zielgruppen) and re-number: col 0 = Zeitschienen, cols 1..n = values.
    df = df.drop(columns=0)
    df.columns = range(df.shape[1])

    # Parse timeslot strings (rows 3–100: 96 regular + 2 summaries).
    timeslot_col = df.iloc[3:101, 0]
    timeslot_df = timeslot_col.apply(
        lambda v: pd.Series(parse_timeslot(str(v))._asdict())
    ).reset_index(drop=True)

    value_cols = df.iloc[3:101, 1:].reset_index(drop=True).astype(float)
    df_wide = pd.concat([timeslot_df, value_cols], axis=1)

    # After dropping col 0 from df, value column k (1..n) in df_wide maps to
    # header_rows column k+1 (the original sheet column before the drop).
    value_col_indices = list(range(1, df.shape[1]))
    metric_map = {k: header_rows.iloc[1, k + 1] for k in value_col_indices}
    station_map = {k: header_rows.iloc[2, k + 1] for k in value_col_indices}

    timeslot_id_vars = [
        "zeitschiene",
        "timeslot_start",
        "timeslot_end",
        "timeslot_duration_minutes",
    ]
    df_melted = df_wide.melt(
        id_vars=timeslot_id_vars,
        value_vars=value_col_indices,
        var_name="col_idx",
        value_name="Wert",
    )
    df_melted["Kenngrösse"] = df_melted["col_idx"].map(metric_map)
    df_melted["Sender"] = df_melted["col_idx"].map(station_map)

    df_long = df_melted.drop(columns=["col_idx"]).reset_index(drop=True)[
        timeslot_id_vars + ["Kenngrösse", "Sender", "Wert"]
    ]
    df_long.insert(0, "Jahr", meta.jahr)
    df_long.insert(1, "Region", meta.region)

    # Normalise string columns: strip whitespace.
    df_long["Sender"] = df_long["Sender"].str.strip()
    df_long["Kenngrösse"] = df_long["Kenngrösse"].str.strip()

    # Resolve Kenngrössen codes to descriptive names.
    df_long["Kenngrösse"] = df_long["Kenngrösse"].map(_KENNGROESSE_MAP)

    return df_long


# ---------------------------------------------------------------------------
# Multi-file loader
# ---------------------------------------------------------------------------


def load_all_files(raw_dir: Path) -> pd.DataFrame:
    """Load all Jahresbericht Excel files in raw_dir and concatenate into one DataFrame."""
    files = sorted(raw_dir.glob("Jahresbericht*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No Jahresbericht files found in {raw_dir}")
    frames = [load_and_transform(f) for f in files]
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    data_dir = Path(__file__).parent.parent.parent / "data"
    raw_dir = data_dir / "raw"
    out_path = data_dir / "Jahresbericht_v2.parquet"

    df = load_all_files(raw_dir)

    pd.set_option("display.max_columns", 10)
    pd.set_option("display.width", 160)
    print(f"Total rows     : {len(df)}")
    print(f"Columns        : {list(df.columns)}")
    print(f"Jahre          : {sorted(df['Jahr'].unique())}")
    print(f"Regionen       : {sorted(df['Region'].unique())}")
    print(f"Kenngrössen    : {df['Kenngrösse'].unique().tolist()}")
    print()
    print(df.head(5).to_string())

    df.to_parquet(out_path, index=False)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
