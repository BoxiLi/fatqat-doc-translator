"""List supported FatQat refs without modifying repositories or RTD settings."""

import json
import re
import subprocess
from site_config import upstream_config


def release_versions(remote_output, pattern):
    return sorted(
        {
            line.split()[1].removeprefix("refs/tags/")
            for line in remote_output.splitlines()
            if len(line.split()) == 2
            and not line.endswith("^{}")
            and re.fullmatch(pattern, line.split()[1].removeprefix("refs/tags/"))
        }
    )


def main():
    config = upstream_config()
    output = subprocess.check_output(
        ["git", "ls-remote", "--tags", config["repository"]], text=True
    )
    print(
        json.dumps(
            {
                "latest": config["ref"],
                "releases": release_versions(output, config["release_pattern"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
