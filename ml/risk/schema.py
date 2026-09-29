"""The contract between the datasets, the trainer and the platform.

Every data source (OULAD, the platform's own footprint) is reduced to one row
per learner *snapshot*: what the learner did in the last ``window`` days, and
whether they left afterwards. The features are deliberately few and behavioural
- no age, gender, region or education - so that the model cannot learn to treat
people differently for who they are, and so that both sources can produce them.

``backend/game/risk.py`` computes the same features for live learners; a backend
test compares its ``FEATURES`` with this file so the two cannot drift apart.
"""

SCHEMA_VERSION = 1

# Raw counts computed by each data adapter.
BASE_FEATURES = (
    "active_days",  # distinct days with any activity in the window
    "events",  # activity count in the window (OULAD: clicks; platform: events + runs)
    "events_last_week",  # the same, over the last 7 days of the window
    "graded_attempted",  # graded attempts in the window
    "graded_failed",  # of those, how many failed
)

# What the model actually sees (derived from the base counts).
FEATURES = (
    "active_days",
    "events",
    "events_last_week",
    "recent_share",  # events_last_week / events: is the learner fading out?
    "graded_attempted",
    "graded_failed_share",
)

LABEL = "label"  # 1 = the learner left / failed afterwards, 0 = stayed / passed
GROUP = "learner"  # rows of one learner must never be split across train and test
PERIOD = "period"  # ordering key for the temporal split (e.g. "2014J")

COLUMNS = (GROUP, PERIOD) + BASE_FEATURES + (LABEL,)


def add_derived(frame):
    """Add ``recent_share`` and ``graded_failed_share`` to a table of base counts."""
    frame = frame.copy()
    events = frame["events"].astype(float)
    frame["recent_share"] = (frame["events_last_week"] / events).where(events > 0, 0.0)
    attempted = frame["graded_attempted"].astype(float)
    frame["graded_failed_share"] = (frame["graded_failed"] / attempted).where(
        attempted > 0, 0.0
    )
    return frame
