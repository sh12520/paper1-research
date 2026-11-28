"""Independent authority entry point with a fixed post-upload light-tier tail guard."""
from pathlib import Path
import sys

import permit_server

EXTRA_TAIL_NS = 12_000_000


def protected_budget(body):
    if (
        body["input_tier"] == "main"
        and (body["accepted_tier"] == "light" or body["post_upload"] in ("auto", "offer"))
    ):
        return {
            **body,
            "tail_budget_ns": {
                **body["tail_budget_ns"],
                "light": body["tail_budget_ns"]["light"] + EXTRA_TAIL_NS,
            },
        }
    return body


class TailProtectedAuthority(permit_server.Authority):
    def _register(self, principal, body, claim, payload):
        # The signed budget stays intact on the wire. Admission and worker start use
        # the stricter local estimate for main-input to light-processing switches.
        return super()._register(principal, protected_budget(body), claim, payload)


if __name__ == "__main__":
    permit_server.Authority = TailProtectedAuthority
    permit_server.serve(Path(sys.argv[1]), Path(sys.argv[2]))
