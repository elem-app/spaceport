from spaceport.globals import edition


def workspace_manifest_file() -> str:
    match edition():
        case "spaceport":
            return "spaceport.yaml"
        case _:
            raise ValueError(f"Invalid edition: {edition()}")


def env_manifest_file() -> str:
    match edition():
        case "spaceport":
            return "sp-env.yaml"
        case _:
            raise ValueError(f"Invalid edition: {edition()}")


def artifact_dir() -> str:
    match edition():
        case "spaceport":
            return "sp-projects"
        case _:
            raise ValueError(f"Invalid edition: {edition()}")
