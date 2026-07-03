"""Run the whole pipeline: fetch everything, build, resolve, export, verify.

On a normal connection the full city pull takes a few minutes.

Run:  python3 pipeline/run_all.py            (fetch + build + verify)
      python3 pipeline/run_all.py --no-fetch (rebuild from existing raw files)
"""
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FETCH = ["fetch_vpi.py", "fetch_opa.py", "fetch_delinquency.py", "fetch_violations.py"]
BUILD = ["build_db.py", "resolve_owners.py", "export_web.py"]
CHECK = [("fetch_vpi.py", "--check"), ("fetch_opa.py", "--check"),
         ("fetch_delinquency.py", "--check"), ("fetch_violations.py", "--check"),
         ("resolve_owners.py", "--check"), ("check_db.py",)]


def run(script, *args):
    print("\n=== %s %s ===" % (script, " ".join(args)))
    result = subprocess.run([sys.executable, os.path.join(HERE, script), *args])
    if result.returncode != 0:
        print("FAILED: %s" % script)
        sys.exit(result.returncode)


def main():
    steps = ([] if "--no-fetch" in sys.argv else FETCH) + BUILD
    for script in steps:
        run(script)
    for script_args in CHECK:
        run(*script_args)
    print("\npipeline complete and verified. start the site with:")
    print("  python3 server/app.py")


if __name__ == "__main__":
    main()
