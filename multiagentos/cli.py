"""Command-line entry point for VYRELON project bootstrap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from installer.init import ProjectInitializer
from profiles.detector import ProfileDetector
from runtime.github_probe import probe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="multiagentos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect", help="detect technology profiles")
    detect.add_argument("path", nargs="?", default=".")

    init = subparsers.add_parser("init", help="initialize VYRELON in a project")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument(
        "--component",
        choices=("vyrelon", "multi-agent", "all"),
        default="all",
        help="install VYRELON, the multi-agent layer, or both",
    )

    github = subparsers.add_parser("github", help="use VYRELON GitHub runtime")
    github_sub = github.add_subparsers(dest="github_command", required=True)
    probe_parser = github_sub.add_parser(
        "probe", help="verify GitHub access for a repository"
    )
    probe_parser.add_argument("repository")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "github" and args.github_command == "probe":
        print(json.dumps(probe(args.repository), indent=2))
        return 0

    root = Path(args.path).expanduser().resolve()
    detector = ProfileDetector()
    detections = detector.detect(root)

    if args.command == "detect":
        print(
            json.dumps(
                [
                    {
                        "profile": result.profile_id,
                        "confidence": result.confidence,
                        "evidence": list(result.evidence),
                    }
                    for result in detections
                ],
                indent=2,
            )
        )
        return 0

    config = ProjectInitializer().apply(
        root,
        detections,
        component=args.component,
    )
    print(f"Initialized VYRELON ({args.component}): {config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
