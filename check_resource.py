import sys

from typing import List
from pathlib import Path

from maa.resource import Resource
from maa.tasker import Tasker, LoggingLevelEnum


def check(dirs: List[Path]) -> bool:
    resource = Resource()

    print(f"Checking {len(dirs)} directories...")

    for dir in dirs:
        print(f"Checking {dir}...")
        # If the directory itself looks like a bundle (contains image/model/pipeline), post it.
        def is_bundle(p: Path) -> bool:
            return (p / "image").exists() and (p / "model").exists() and (p / "pipeline").exists()

        bundles = []
        if is_bundle(dir):
            bundles.append(dir)
        else:
            # Look for child directories that are bundles (one-level deep). This covers the new
            # structure where resources live under a category like 'base'.
            for child in dir.iterdir():
                if child.is_dir() and is_bundle(child):
                    bundles.append(child)

        if not bundles:
            print(f"No resource bundles found under {dir} (expected image/, model/, pipeline/).")
            return False

        for b in bundles:
            print(f"Posting bundle {b}...")
            status = resource.post_bundle(b).wait().status
            if not status.succeeded:
                print(f"Failed to check bundle {b}.")
                return False

    print("All directories checked.")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python configure.py <directory>")
        sys.exit(1)

    Tasker.set_stdout_level(LoggingLevelEnum.All)

    dirs = [Path(arg) for arg in sys.argv[1:]]
    if not check(dirs):
        sys.exit(1)


if __name__ == "__main__":
    main()
