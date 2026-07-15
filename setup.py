"""Custom setuptools build command that compiles the React frontend."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class BuildFrontend(_build_py):
    """build_py subclass that runs `npm ci && npm run build` before packaging."""

    def run(self) -> None:
        root = Path(__file__).parent
        web_dir = root / "web"
        dist_dir = web_dir / "dist"
        target = root / "sample_key_indexer" / "web_dist"

        if web_dir.exists():
            # Skip npm if dist is already populated (e.g. CI pre-builds).
            if dist_dir.exists() and any(dist_dir.iterdir()):
                print("setup.py: web/dist/ already exists — skipping npm build.")
            else:
                print("setup.py: building React frontend…")
                for cmd in (
                    ["npm", "ci", "--prefer-offline"],
                    ["npm", "run", "build"],
                ):
                    result = subprocess.run(cmd, cwd=str(web_dir), check=False)
                    if result.returncode != 0:
                        print(
                            f"setup.py: Warning — frontend build step failed"
                            f" ({' '.join(cmd)})."
                            " sample-key-indexer-web will fall back to the"
                            " legacy web_static/ assets.",
                            file=sys.stderr,
                        )
                        super().run()
                        return

            # Copy web/dist/ → sample_key_indexer/web_dist/ so it is
            # bundled as ordinary package data in regular (non-editable)
            # installs.
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(str(dist_dir), str(target))
            print(f"setup.py: copied web/dist/ → {target.relative_to(root)}")

        super().run()


setup(cmdclass={"build_py": BuildFrontend})
