import csv
import io

REQUIRED_HEADERS = [
    "node_id","discord_id","short_name","long_name","node_type","node_role",
    "hardware_model","general_location","location_set","power_source",
    "is_attended","antenna_above_roofline","antenna_dbi","antenna_height","notes"
]

def parse_csv_string(csv_string: str) -> list[dict]:
    """
    Parse a CSV string into a list of dicts with required headers.
    Raises ValueError if headers are missing/mismatched or rows malformed.
    """
    if not csv_string.strip():
        raise ValueError("Empty CSV string")

    reader = csv.reader(io.StringIO(csv_string.strip()))
    rows = list(reader)

    if not rows or len(rows[0]) == 0:
        raise ValueError("Invalid CSV format")

    headers = rows[0]

    if headers != REQUIRED_HEADERS:
        raise ValueError(
            f"CSV must contain exact headers:\n{REQUIRED_HEADERS}\nGot:\n{headers}"
        )

    data_rows = rows[1:]
    col_count = len(REQUIRED_HEADERS)

    for i, row in enumerate(data_rows, start=2):
        if len(row) != col_count:
            raise ValueError(
                f"Row {i} has {len(row)} columns, expected {col_count}"
            )

    return [dict(zip(headers, row)) for row in data_rows]

def filter_node_ids_length(data: list[dict]) -> list[dict]:
    """
    Filter entries where 'node_id' has exactly 8 characters.
    """
    return [entry for entry in data if len(entry.get("node_id", "")) == 8]
