import os
import sys
import glob
import shutil
import argparse


def clean(include_data=False):
    files = ["sorted_cpp.txt", "sorted_py.txt"]
    if include_data:
        files.append("data.csv")

    dirs = ["temp_chunks_cpp", "temp_chunks_py"]
    removed, errors = [], []

    for f in files:
        try:
            if os.path.exists(f):
                os.remove(f)
                removed.append(f)
        except OSError as e:
            errors.append("Failed to delete %s: %s" % (f, e))

    for d in dirs:
        try:
            if os.path.exists(d):
                shutil.rmtree(d)
                removed.append(d + "/")
        except OSError as e:
            errors.append("Failed to delete dir %s: %s" % (d, e))

    for f in glob.glob("*.tmp"):
        try:
            os.remove(f)
            removed.append(f)
        except OSError as e:
            errors.append("Failed to delete %s: %s" % (f, e))

    print("=== Cleanup Report ===")
    print("Removed: %s" % (", ".join(removed) if removed else "nothing"))
    if errors:
        print("Errors: %s" % ", ".join(errors))
    print("Done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Also delete data.csv")
    args = ap.parse_args()
    clean(include_data=args.all)
