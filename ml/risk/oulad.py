"""Turn the Open University Learning Analytics Dataset (OULAD) into snapshots.

OULAD (Kuzilek, Hlosta, Zdrahal, 2017; CC BY 4.0) describes ~32,000 students on
22 course presentations. Files used, all relative to one directory:

    studentInfo.csv, studentRegistration.csv, studentVle.csv,
    studentAssessment.csv, assessments.csv

One row per (module, presentation, student) is produced. Features come from the
first ``window_days`` days of the presentation; the label is the final outcome
(Fail or Withdrawn = 1, Pass or Distinction = 0).

Students who had already unregistered before the window ended are dropped:
their outcome is known and predicting it would be leakage, not forecasting.
"""

from pathlib import Path

import pandas as pd

from .schema import BASE_FEATURES, COLUMNS, GROUP, LABEL, PERIOD

PASS_MARK = 40  # OULAD scores are 0-100, 40 is the pass mark
BAD_OUTCOMES = {"Fail", "Withdrawn"}
KEY = ["code_module", "code_presentation", "id_student"]


def _read(directory, name, **kwargs):
    path = Path(directory) / name
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - is this the OULAD directory?")
    return pd.read_csv(path, **kwargs)


def build_snapshots(directory, window_days=28):
    """One row per student with ``COLUMNS`` (base counts + label)."""
    info = _read(directory, "studentInfo.csv")
    registration = _read(directory, "studentRegistration.csv")
    clicks = _read(directory, "studentVle.csv")
    submissions = _read(directory, "studentAssessment.csv")
    assessments = _read(directory, "assessments.csv")

    left_already = registration["date_unregistration"].notna() & (
        registration["date_unregistration"] < window_days
    )
    staying = registration.loc[~left_already, KEY]
    students = info[KEY + ["final_result"]].merge(staying, on=KEY, how="inner")
    students[LABEL] = students["final_result"].isin(BAD_OUTCOMES).astype(int)

    in_window = clicks[(clicks["date"] >= 0) & (clicks["date"] < window_days)]
    last_week = in_window[in_window["date"] >= window_days - 7]
    activity = (
        in_window.groupby(KEY)
        .agg(events=("sum_click", "sum"), active_days=("date", "nunique"))
        .reset_index()
    )
    recent = (
        last_week.groupby(KEY)["sum_click"]
        .sum()
        .rename("events_last_week")
        .reset_index()
    )

    graded = submissions.merge(
        assessments[["id_assessment", "code_module", "code_presentation"]],
        on="id_assessment",
        how="inner",
    )
    graded = graded[
        (graded["is_banked"] == 0)  # credit transferred from earlier study
        & (graded["date_submitted"] < window_days)
        & graded["score"].notna()
    ]
    graded = graded.assign(failed=(graded["score"] < PASS_MARK).astype(int))
    results = (
        graded.groupby(KEY)
        .agg(graded_attempted=("score", "size"), graded_failed=("failed", "sum"))
        .reset_index()
    )

    table = (
        students.merge(activity, on=KEY, how="left")
        .merge(recent, on=KEY, how="left")
        .merge(results, on=KEY, how="left")
    )
    table[list(BASE_FEATURES)] = table[list(BASE_FEATURES)].fillna(0).astype(int)
    table[GROUP] = (
        table["code_module"]
        + "-"
        + table["code_presentation"]
        + "-"
        + table["id_student"].astype(str)
    )
    table[PERIOD] = table["code_presentation"]
    return table[list(COLUMNS)].reset_index(drop=True)
