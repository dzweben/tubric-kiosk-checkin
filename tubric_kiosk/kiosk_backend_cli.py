#!/usr/bin/env python3
import json
import sys

import survey


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        sys.stderr.write(f"Invalid JSON input: {exc}\n")
        sys.exit(1)

    guid, action, _, _ = survey.submit_checkin(payload)
    sys.stdout.write(json.dumps({"guid": guid, "action": action}))


if __name__ == "__main__":
    main()
