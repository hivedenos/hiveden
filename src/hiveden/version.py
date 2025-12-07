import os
import subprocess

# This variable is intended to be overwritten during the build/release process
__version__ = "test"

def get_version() -> str:
    """
    Returns the current version of the application.
    Priorities:
    1. Explicitly set __version__ (if not "test")
    2. Git commit hash (if inside a git repo)
    3. Fallback "test"
    """
    global __version__
    
    if __version__ != "test":
        return __version__

    # Try to get git commit hash
    try:
        # Check if we are in a git repository
        with open(os.devnull, 'w') as devnull:
            # git rev-parse --short HEAD
            cmd = ["git", "rev-parse", "--short", "HEAD"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return "test"
