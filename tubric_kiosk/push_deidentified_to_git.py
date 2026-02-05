#!/usr/bin/env python3
import argparse
import os
import subprocess
from datetime import datetime


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(
        description="Push de-identified TUBRIC kiosk data to a private Git repo."
    )
    parser.add_argument("repo_path", help="Path to the local clone of the private repo")
    parser.add_argument(
        "--file",
        default=os.path.join(os.path.dirname(__file__), "..", "db_exports", "deidentified_visits.csv"),
        help="Path to de-identified CSV file (default: ../db_exports/deidentified_visits.csv)",
    )
    args = parser.parse_args()

    repo_path = os.path.abspath(args.repo_path)
    src_file = os.path.abspath(args.file)

    if not os.path.exists(repo_path):
        raise SystemExit(f"Repo path not found: {repo_path}")
    if not os.path.exists(src_file):
        raise SystemExit(f"De-identified file not found: {src_file}")

    src_file = os.path.abspath(src_file)
    if src_file.startswith(repo_path + os.sep):
        rel_path = os.path.relpath(src_file, repo_path)
    else:
        dest_file = os.path.join(repo_path, os.path.basename(src_file))
        with open(src_file, "rb") as src, open(dest_file, "wb") as dst:
            dst.write(src.read())
        rel_path = os.path.basename(dest_file)

    run(["git", "add", rel_path], cwd=repo_path)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit = run(["git", "commit", "-m", f"TUBRIC de-identified export {timestamp}"], cwd=repo_path)
    if commit.returncode != 0:
        # Likely no changes to commit
        print(commit.stderr.strip() or "No changes to commit.")
        return

    push = run(["git", "push"], cwd=repo_path)
    if push.returncode != 0:
        print(push.stderr.strip() or "Push failed.")
        raise SystemExit(1)
    print("Push complete.")


if __name__ == "__main__":
    main()
