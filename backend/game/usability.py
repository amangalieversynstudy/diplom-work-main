"""Usability of the dashboard for the teacher, measured with the System Usability Scale (SUS).

SUS (Brooke, 1996) is ten statements rated 1 (strongly disagree) to 5 (strongly agree); odd statements are
worded positively, even ones negatively. The score runs 0-100; about 68 is the average over many systems,
80 and above is good. It is a short standard questionnaire, so the pilot's result can be compared with others.
The statements themselves live in the frontend dictionaries (Russian and English).
"""

from django.db.models import Max

from .models import UsabilityResponse

ITEMS = 10
AVERAGE = 68  # the usual benchmark (Sauro, Lewis)
GOOD = 80


def sus_score(answers):
    """SUS score of ten ratings 1-5, or ValueError when the answers are not that."""
    if (
        not isinstance(answers, (list, tuple))
        or len(answers) != ITEMS
        or not all(isinstance(a, int) and not isinstance(a, bool) and 1 <= a <= 5 for a in answers)
    ):
        raise ValueError(f"expected {ITEMS} ratings from 1 to 5")
    points = sum((a - 1) if index % 2 == 0 else (5 - a) for index, a in enumerate(answers))
    return points * 2.5


def verdict(score):
    if score is None:
        return None
    if score >= GOOD:
        return "good"
    if score >= AVERAGE:
        return "average"
    return "below_average"


def latest_by_user():
    """{user_id: UsabilityResponse}: a teacher who answered twice counts once, with the later answer."""
    newest = UsabilityResponse.objects.values("user_id").annotate(last=Max("id")).values("last")
    return {r.user_id: r for r in UsabilityResponse.objects.filter(id__in=newest)}


def usability_summary():
    """{respondents, mean, lowest, highest, verdict, average_benchmark} over the teachers' latest answers."""
    scores = [response.score for response in latest_by_user().values()]
    mean = round(sum(scores) / len(scores), 1) if scores else None
    return {
        "respondents": len(scores),
        "mean": mean,
        "lowest": min(scores) if scores else None,
        "highest": max(scores) if scores else None,
        "verdict": verdict(mean),
        "average_benchmark": AVERAGE,
    }
