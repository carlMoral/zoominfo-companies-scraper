import csv
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List

from ..extractors.data_utils import ensure_directory, to_serializable

logger = logging.getLogger(__name__)

class DataExporter:
    """
    Export company records into one or more file formats.
    Supported formats: json, csv.
    """

    def __init__(
        self,
        output_dir: str,
        formats: Iterable[str],
        filename_prefix: str = "zoominfo_companies",
    ) -> None:
        self.output_dir = output_dir
        self.formats = [fmt.lower() for fmt in formats]
        self.filename_prefix = filename_prefix

    def export(self, companies: List[Dict[str, Any]]) -> None:
        ensure_directory(self.output_dir)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        if "json" in self.formats:
            self._export_json(companies, timestamp)

        if "csv" in self.formats:
            self._export_csv(companies, timestamp)

    def _export_json(
        self, companies: List[Dict[str, Any]], timestamp: str
    ) -> None:
        path = os.path.join(
            self.output_dir, f"{self.filename_prefix}_{timestamp}.json"
        )
        serializable = [to_serializable(c) for c in companies]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
            logger.info("Exported %d records to JSON: %s", len(companies), path)
        except OSError as exc:
            logger.error("Failed to write JSON output to %s: %s", path, exc)
            raise

    def _export_csv(
        self, companies: List[Dict[str, Any]], timestamp: str
    ) -> None:
        if not companies:
            logger.warning("No records to export to CSV.")
            return

        # Determine union of all keys for header
        header_keys: List[str] = sorted(
            {key for company in companies for key in company.keys()}
        )

        path = os.path.join(
            self.output_dir, f"{self.filename_prefix}_{timestamp}.csv"
        )
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=header_keys)
                writer.writeheader()
                for company in companies:
                    row = {
                        key: self._format_csv_value(company.get(key))
                        for key in header_keys
                    }
                    writer.writerow(row)
            logger.info("Exported %d records to CSV: %s", len(companies), path)
        except OSError as exc:
            logger.error("Failed to write CSV output to %s: %s", path, exc)
            raise

    @staticmethod
    def _format_csv_value(value: Any) -> Any:
        if isinstance(value, (list, dict)):
            return json.dumps(to_serializable(value), ensure_ascii=False)
        return value