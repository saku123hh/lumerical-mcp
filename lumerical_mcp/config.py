import os
import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    lumerical_root: Path
    host: str = "127.0.0.1"
    port: int = 8000
    transport: str = "streamable-http"
    work_dir: Path = field(default_factory=Path.cwd)
    log_level: str = "INFO"

    @property
    def lumerical_api_python(self) -> Path:
        return self.lumerical_root / "api" / "python"

    @property
    def lumerical_bin(self) -> Path:
        return self.lumerical_root / "bin"

    @classmethod
    def load(cls) -> "Config":
        lumerical_root = os.environ.get("LUMERICAL_ROOT")
        if not lumerical_root:
            raise RuntimeError(
                "LUMERICAL_ROOT environment variable not set. "
                "Point it to your Lumerical installation directory, e.g.: "
                "  Windows: D:\\Program Files\\ANSYS Inc\\v251\\Lumerical "
                "  Linux: /opt/lumerical/v251"
            )
        root = Path(lumerical_root).expanduser().resolve()
        if not root.exists():
            raise RuntimeError(f"LUMERICAL_ROOT path does not exist: {root}")

        config_file = Path.home() / ".config" / "lumerical-mcp" / "config.json"
        file_cfg = {}
        if config_file.exists():
            try:
                file_cfg = json.loads(config_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        def get(key: str, default):
            return os.environ.get(key) or file_cfg.get(key) or default

        return cls(
            lumerical_root=root,
            host=get("MCP_HOST", "127.0.0.1"),
            port=int(get("MCP_PORT", "8000")),
            transport=get("MCP_TRANSPORT", "streamable-http"),
            work_dir=Path(get("MCP_WORK_DIR", str(Path.cwd()))).expanduser().resolve(),
            log_level=get("MCP_LOG_LEVEL", "INFO"),
        )