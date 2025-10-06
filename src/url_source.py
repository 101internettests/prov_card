import glob
import os
from typing import Dict, List

from openpyxl import load_workbook


def read_urls_from_txt_dir(dir_path: str) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for file_path in sorted(glob.glob(os.path.join(dir_path, "*.txt"))):
        group = os.path.splitext(os.path.basename(file_path))[0]
        urls: List[str] = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                urls.append(s)
        if urls:
            groups[group] = urls
    return groups


def read_urls_from_xlsx(file_path: str) -> Dict[str, List[str]]:
    wb = load_workbook(filename=file_path, read_only=True, data_only=True)
    groups: Dict[str, List[str]] = {}
    for ws in wb.worksheets:
        group = ws.title
        urls: List[str] = []
        for row in ws.iter_rows(values_only=True):
            if not row:
                continue
            cell = row[0]
            if not cell:
                continue
            s = str(cell).strip()
            if not s or s.startswith("#"):
                continue
            urls.append(s)
        if urls:
            groups[group] = urls
    return groups


def load_groups(urls_dir_or_file: str) -> Dict[str, List[str]]:
    """
    Если путь — директория: читаем все *.txt как группы.
    Если путь — .xlsx файл: каждый лист — группа, первая колонка — URL.
    """
    if os.path.isdir(urls_dir_or_file):
        return read_urls_from_txt_dir(urls_dir_or_file)
    if os.path.isfile(urls_dir_or_file) and urls_dir_or_file.lower().endswith(".xlsx"):
        return read_urls_from_xlsx(urls_dir_or_file)
    raise FileNotFoundError(f"Не найдена директория/файл URL: {urls_dir_or_file}")
