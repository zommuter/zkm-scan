"""zkm-scan — filesystem-discovery shim; delegates to the zkm_scan package.

Loaded by core when the plugin is filesystem-discovered (dev-symlink workflow).
Core's _inject_plugin_venv (SB2) adds plugins/zkm-scan/src/ to sys.path before
loading this file, making zkm_scan importable here.
"""

from zkm_scan.convert import convert  # noqa: F401
