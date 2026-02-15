from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ParsedProxy:
    host: str
    port: int
    protocol: str = "http"
    username: str | None = None
    password: str | None = None


def parse_proxy_list(text: str, default_protocol: str = "http") -> list[ParsedProxy]:
    """Parse multi-format proxy list. Auto-detects format per line."""
    results = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        results.append(parse_single_line(line, default_protocol))
    return results


def parse_single_line(line: str, default_protocol: str) -> ParsedProxy:
    """Parse a single proxy line. Supports:
    1. protocol://user:pass@host:port
    2. protocol://host:port
    3. host:port:user:pass
    4. host:port
    """
    # Format 1 & 2: URL-style with protocol scheme
    if "://" in line:
        parsed = urlparse(line)
        protocol = parsed.scheme or default_protocol
        host = parsed.hostname or ""
        port = parsed.port or (1080 if protocol == "socks5" else 8080)
        username = parsed.username or None
        password = parsed.password or None
        return ParsedProxy(
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            password=password,
        )

    # Format 3: host:port@user:pass
    if "@" in line:
        host_port, user_pass = line.split("@", 1)
        hp_parts = host_port.rsplit(":", 1)
        up_parts = user_pass.split(":", 1)
        return ParsedProxy(
            host=hp_parts[0],
            port=int(hp_parts[1]),
            protocol=default_protocol,
            username=up_parts[0],
            password=up_parts[1] if len(up_parts) > 1 else None,
        )

    # Format 4 & 5: colon-separated
    parts = line.split(":")
    if len(parts) == 4:
        # host:port:user:pass
        return ParsedProxy(
            host=parts[0],
            port=int(parts[1]),
            protocol=default_protocol,
            username=parts[2],
            password=parts[3],
        )
    elif len(parts) == 2:
        # host:port
        return ParsedProxy(
            host=parts[0],
            port=int(parts[1]),
            protocol=default_protocol,
        )
    else:
        raise ValueError(f"Unrecognized proxy format: {line}")
