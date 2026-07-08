"""竞赛文档结构化信息抽取（C 题第一问）。"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd

from first_problem.pdf_preprocessor import PDFPreprocessor
from first_problem.regex_debugger import RegexDebugger


def extract_competition_info_v2(pdf_path: str | Path) -> dict[str, str]:
    """从单个 PDF 提取赛项结构化字段。"""
    preprocessor = PDFPreprocessor(pdf_path)
    clean_text = preprocessor.extract_text_with_layout()

    debugger = RegexDebugger()

    patterns = {
        "赛项名称": r"(.*?挑战赛)",
        "赛道": r"(\w+专项赛)",
        "发布时间": r"\d{4}年\d{1,2}月",
        "报名时间": (
            r"(报名时间|报名起始时间)[：\s]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
            r"\s*-\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
        ),
        "组织单位": r"(?s)\s*(泰迪杯[\w\u4e00-\u9fa5]+委员会|中国[\w\u4e00-\u9fa5]+服务中心)",
        "官网": r"(https?://[^/\s]+)",
    }

    results = debugger.test_pattern(clean_text, patterns)

    competition_info: dict[str, str] = {}
    for key, data in results.items():
        if key == "报名时间":
            if data["matches"]:
                match = data["matches"][0]
                start_year, start_month, start_day, end_month, end_day = match[1:6]
                competition_info[key] = (
                    f"{start_year}年{start_month}月{start_day}日-{end_month}月{end_day}日"
                )
            else:
                competition_info[key] = ""
        elif key == "官网":
            if data["matches"]:
                match = re.sub(r"[。；]", "", data["matches"][0])
                competition_info[key] = match.replace("\n", "").strip()
            else:
                competition_info[key] = ""
        elif data["matches"]:
            match = data["matches"][0]
            if isinstance(match, tuple):
                match = "".join(match)
            competition_info[key] = match.replace("\n", "").strip()
        else:
            competition_info[key] = ""
    return competition_info


def process_competition_docs(directory: str | Path) -> pd.DataFrame:
    """批量处理目录下所有 PDF。"""
    competitions: list[dict[str, str]] = []
    directory = Path(directory)

    for file_path in sorted(directory.glob("*.pdf")):
        competitions.append(extract_competition_info_v2(file_path))

    return pd.DataFrame(competitions)


def fill_empty_values(df: pd.DataFrame) -> pd.DataFrame:
    """填充发布时间和报名时间的空白值。"""
    for index, row in df.iterrows():
        if row["发布时间"] == "":
            same_name_rows = df[df["赛项名称"] == row["赛项名称"]]
            non_empty_publish_times = same_name_rows[same_name_rows["发布时间"] != ""]["发布时间"]
            if not non_empty_publish_times.empty:
                df.at[index, "发布时间"] = non_empty_publish_times.iloc[0]
        if row["报名时间"] == "":
            same_name_rows = df[df["赛项名称"] == row["赛项名称"]]
            non_empty_signup_times = same_name_rows[same_name_rows["报名时间"] != ""]["报名时间"]
            if not non_empty_signup_times.empty:
                df.at[index, "报名时间"] = non_empty_signup_times.iloc[0]
    return df


def correct_signup_times(df: pd.DataFrame) -> pd.DataFrame:
    """按赛项名称统一发布时间。"""
    for name in df["赛项名称"].unique():
        same_name_rows = df[df["赛项名称"] == name]
        non_empty_signup_rows = same_name_rows[same_name_rows["发布时间"] != ""]
        if not non_empty_signup_rows.empty:
            first_signup_time = non_empty_signup_rows.iloc[0]["发布时间"]
            df.loc[df["赛项名称"] == name, "发布时间"] = first_signup_time
    return df


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    pdf_directory = project_root / "data"
    output_path = Path(__file__).resolve().parent / "result_1.xlsx"

    if not pdf_directory.is_dir():
        raise FileNotFoundError(f"未找到 PDF 目录: {pdf_directory}")

    competition_df = process_competition_docs(pdf_directory)
    competition_df = fill_empty_values(competition_df)
    competition_df = correct_signup_times(competition_df)

    print(competition_df)
    competition_df.to_excel(output_path, index=False)
    print(f"结果已保存: {output_path}")


if __name__ == "__main__":
    main()
