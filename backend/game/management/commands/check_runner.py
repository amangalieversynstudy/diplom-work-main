"""Does code really run on this server? Run it the day before the demonstration, on the server itself.

    python manage.py check_runner

It sends a tiny program through the same path a learner's "Run" button uses (Docker sandbox, else Judge0)
and says what happened and how long it took. ``pilot_check`` only reads the settings; this one proves it.
"""

import time

from django.core.management.base import BaseCommand, CommandError

from game import runner

PROGRAM = "print(sum(range(1, 11)))"
EXPECTED = "55"


class Command(BaseCommand):
    help = "Run a tiny program through the learners' code runner and report whether it works."

    def add_arguments(self, parser):
        parser.add_argument("--times", type=int, default=3, help="How many runs to make (default 3).")

    def handle(self, *args, **options):
        failures = 0
        seconds = []
        for n in range(1, max(1, options["times"]) + 1):
            started = time.time()
            result = runner.execute_python_code(PROGRAM)
            took = time.time() - started
            seconds.append(took)
            ok = result.get("status") == "success" and result.get("output", "").strip() == EXPECTED
            failures += 0 if ok else 1
            line = f"run {n}: {'ok' if ok else 'FAILED'} in {took:.1f} s"
            if not ok:
                line += f" ({(result.get('output') or '')[:120]!r})"
            self.stdout.write((self.style.SUCCESS if ok else self.style.ERROR)(line))
        if failures:
            raise CommandError(
                f"{failures} of {len(seconds)} runs failed: learners will see «проверяющая служба недоступна». "
                "Check RUNNER_JUDGE0_URL / the Docker socket and the server's outgoing network; details are in the log."
            )
        slow = max(seconds)
        self.stdout.write(self.style.SUCCESS(f"Code runs here (slowest run {slow:.1f} s)."))
        if slow > 8:
            self.stdout.write(self.style.WARNING("A run is slow: several learners pressing Run together will wait."))
