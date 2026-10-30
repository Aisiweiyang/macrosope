"""数据导入器：CSV / Excel / JSON / Parquet。"""
from macrosope.importers.base import PreviewResult, normalize_dataframe, read_file
from macrosope.importers.csv_reader import read_csv
from macrosope.importers.excel_reader import list_sheets, read_excel
from macrosope.importers.json_reader import read_json
from macrosope.importers.parquet_reader import read_parquet

__all__ = [
    "PreviewResult",
    "list_sheets",
    "normalize_dataframe",
    "read_csv",
    "read_excel",
    "read_file",
    "read_json",
    "read_parquet",
]
