import json
from pathlib import Path
from typing import Any, Iterable, List, Dict

class JSONExporter:
    """
    Writes scraped company data into a JSON file.
    """

    def __init__(self, output_path: Path | str) -> None:
        self.output_path = Path(output_path).resolve()

    def export(self, records: Iterable[Dict[str, Any]]) -> None:
        records_list: List[Dict[str, Any]] = list(records)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with self.output_path.open("w", encoding="utf-8") as f:
            json.dump(records_list, f, indent=2, ensure_ascii=False)