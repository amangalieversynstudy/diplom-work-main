"""The OULAD adapter, on a hand-made miniature of the real files."""

import pandas as pd
import pytest

from risk import oulad
from risk.schema import COLUMNS, GROUP, LABEL


@pytest.fixture
def directory(tmp_path):
    def write(name, rows, columns):
        pd.DataFrame(rows, columns=columns).to_csv(tmp_path / name, index=False)

    def student(number, outcome):
        return ["AAA", "2014J", number, outcome]

    write(
        "studentInfo.csv",
        [
            student(1, "Pass"),
            student(2, "Fail"),
            student(3, "Withdrawn"),
            student(4, "Distinction"),
            student(5, "Withdrawn"),
        ],
        ["code_module", "code_presentation", "id_student", "final_result"],
    )
    write(
        "studentRegistration.csv",
        [
            ["AAA", "2014J", 1, -10, None],
            ["AAA", "2014J", 2, -5, None],
            ["AAA", "2014J", 3, -5, 10],  # gone before the window ends: dropped
            ["AAA", "2014J", 4, -1, None],
            ["AAA", "2014J", 5, -1, 40],  # left after the window: still a forecast
        ],
        ["code_module", "code_presentation", "id_student", "date_registration",
         "date_unregistration"],
    )
    click = lambda n, day, clicks: ["AAA", "2014J", n, 1, day, clicks]  # noqa: E731
    write(
        "studentVle.csv",
        [
            click(1, 1, 10), click(1, 2, 5), click(1, 25, 7),
            click(1, 30, 99),  # after the window
            click(1, -5, 99),  # before the course started
            click(2, 3, 2),
            click(5, 4, 1),
        ],
        ["code_module", "code_presentation", "id_student", "id_site", "date", "sum_click"],
    )
    write(
        "assessments.csv",
        [["AAA", "2014J", 100, "TMA", 20, 10], ["AAA", "2014J", 101, "TMA", 60, 20]],
        ["code_module", "code_presentation", "id_assessment", "assessment_type", "date", "weight"],
    )
    write(
        "studentAssessment.csv",
        [
            [100, 1, 20, 0, 80],
            [100, 2, 10, 0, 30],  # below the pass mark
            [100, 4, 5, 1, 90],  # banked credit: not this course's work
            [101, 1, 50, 0, 70],  # after the window
        ],
        ["id_assessment", "id_student", "date_submitted", "is_banked", "score"],
    )
    return tmp_path


def rows(directory, window=28):
    table = oulad.build_snapshots(directory, window)
    return table.set_index(GROUP)


def test_columns_and_who_is_kept(directory):
    table = oulad.build_snapshots(directory)
    assert list(table.columns) == list(COLUMNS)
    assert sorted(table[GROUP]) == ["AAA-2014J-1", "AAA-2014J-2", "AAA-2014J-4", "AAA-2014J-5"]


def test_activity_counts_only_the_window(directory):
    first = rows(directory).loc["AAA-2014J-1"]
    assert first["events"] == 22  # 10 + 5 + 7; days -5 and 30 are outside
    assert first["active_days"] == 3
    assert first["events_last_week"] == 7  # only day 25 is in days 21..27
    assert first[LABEL] == 0


def test_graded_attempts_skip_banked_and_late_work(directory):
    table = rows(directory)
    assert (table.loc["AAA-2014J-1", "graded_attempted"], table.loc["AAA-2014J-1", "graded_failed"]) == (1, 0)
    assert (table.loc["AAA-2014J-2", "graded_attempted"], table.loc["AAA-2014J-2", "graded_failed"]) == (1, 1)
    assert table.loc["AAA-2014J-4", "graded_attempted"] == 0  # only a banked score


def test_silent_students_get_zeros_and_labels_follow_the_outcome(directory):
    table = rows(directory)
    silent = table.loc["AAA-2014J-4"]
    assert (silent["events"], silent["active_days"]) == (0, 0)
    assert silent[LABEL] == 0  # Distinction
    assert table.loc["AAA-2014J-2", LABEL] == 1  # Fail
    assert table.loc["AAA-2014J-5", LABEL] == 1  # Withdrew on day 40, after the window


def test_leaving_before_the_window_ends_is_leakage_not_forecasting(directory):
    # student 3 unregistered on day 10
    assert "AAA-2014J-3" not in set(oulad.build_snapshots(directory, 28)[GROUP])
    assert "AAA-2014J-3" in set(oulad.build_snapshots(directory, 8)[GROUP])


def test_missing_files_are_reported_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="OULAD"):
        oulad.build_snapshots(tmp_path)
