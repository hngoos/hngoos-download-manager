from hngoos_dm.bridge import main

if __name__ == "__main__":
    import json
    import os
    import sys
    from pathlib import Path
    # The isolated development bridge keeps requests in the live app's database.
    # Release installations do not ship this sidecar and use the normal data directory.
    config = Path(sys.executable).parent/"bridge-data.json"
    if getattr(sys, "frozen", False) and config.is_file():
        value = json.loads(config.read_text(encoding="utf-8"))
        directory = Path(value["directory"])
        if not directory.is_absolute():
            raise ValueError("Native data directory must be absolute")
        os.environ["HDM_DATA_DIR"] = str(directory)
    main()
