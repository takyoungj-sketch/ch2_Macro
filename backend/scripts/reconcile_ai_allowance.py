"""Release a verified abandoned reservation. Never run against a live worker.
python -m scripts.reconcile_ai_allowance REQUEST_ID --operator NAME --reason TEXT --worker-stopped
"""
import argparse
from app.ai.allowances import release_abandoned
from app.platform.db import get_platform_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_id")
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--worker-stopped", action="store_true", required=True)
    args = parser.parse_args()
    release_abandoned(get_platform_engine(), args.request_id, args.operator, args.reason)
    print("Reservation released; audit adjustment recorded.")


if __name__ == "__main__":
    main()
