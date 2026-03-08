import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ParsedProxy:
    host: str
    port: int
    protocol: str = "http"
    username: str | None = None
    password: str | None = None


_SOCKS_PORTS = set(range(1080, 1090))
_HTTPS_PORTS = {443, 8443, 8444}

# Matches an IPv4 address or a hostname (containing a dot or starting with a letter)
_IP_RE = re.compile(
    r"^(?:\d{1,3}\.){3}\d{1,3}$"  # IPv4
    r"|^[a-zA-Z][\w.-]+$"          # hostname
)


def _guess_protocol(port: int) -> str:
    """Guess protocol from well-known port numbers."""
    if port in _SOCKS_PORTS:
        return "socks5"
    if port in _HTTPS_PORTS:
        return "https"
    return "http"


def _is_port(s: str) -> bool:
    """Check if string is a valid port number."""
    try:
        p = int(s)
        return 0 < p <= 65535
    except ValueError:
        return False


def _looks_like_host(s: str) -> bool:
    """Check if string looks like a host (IP or hostname)."""
    return bool(_IP_RE.match(s))


def parse_proxy_list(text: str) -> list[ParsedProxy]:
    """Parse multi-format proxy list. Auto-detects format and protocol per line."""
    results = []
    errors = []
    for i, line in enumerate(text.strip().splitlines(), 1):
        line = line.strip().rstrip("\r")
        if not line or line.startswith("#"):
            continue
        try:
            results.append(parse_single_line(line))
        except ValueError:
            errors.append(f"Line {i}: {line}")
    if errors and not results:
        raise ValueError(f"No valid proxies found. Errors:\n" + "\n".join(errors))
    return results


def parse_single_line(line: str) -> ParsedProxy:
    """Parse a single proxy line. Auto-detects format:
    - protocol://user:pass@host:port  (URL-style with auth)
    - protocol://host:port            (URL-style no auth)
    - host:port@user:pass             (@ separator, host first)
    - user:pass@host:port             (@ separator, auth first)
    - host:port:user:pass             (colon-separated, host first)
    - user:pass:host:port             (colon-separated, auth first)
    - host:port:user:pass:extra:...   (extra trailing fields ignored)
    - host port user pass             (space/tab separated)
    - host,port,user,pass             (CSV)
    - host port                       (space separated, no auth)
    - host,port                       (CSV, no auth)
    - [ipv6]:port                     (IPv6 in brackets)
    """
    # --- URL-style: has :// scheme ---
    if "://" in line:
        return _parse_url(line)

    # --- IPv6 in brackets: [::1]:port or [::1]:port@user:pass ---
    if line.startswith("["):
        return _parse_ipv6_brackets(line)

    # --- Detect separator: comma, whitespace, or colon ---
    # CSV (comma-separated)
    if "," in line and ":" not in line.split(",")[0]:
        return _parse_delimited(line.split(","))

    # Space/tab separated (but not if it looks like host:port with spaces around)
    if ("\t" in line or "  " in line or (
        " " in line and ":" not in line
    )):
        return _parse_delimited(line.split())

    # Single space: "host:port user pass" or "host port"
    if " " in line and ":" in line:
        # Could be "host:port user pass" format
        space_parts = line.split()
        if len(space_parts) >= 2 and ":" in space_parts[0]:
            hp = space_parts[0].split(":")
            if len(hp) == 2 and _is_port(hp[1]):
                port = int(hp[1])
                user = space_parts[1] if len(space_parts) > 1 else None
                pwd = space_parts[2] if len(space_parts) > 2 else None
                return ParsedProxy(
                    host=hp[0], port=port, protocol=_guess_protocol(port),
                    username=user, password=pwd,
                )
        # "host port" with no colon
        if len(space_parts) >= 2 and _is_port(space_parts[1]):
            return _parse_delimited(space_parts)

    # --- @ separator ---
    if "@" in line:
        return _parse_at_format(line)

    # --- Colon-separated ---
    parts = line.split(":")
    return _parse_colon_parts(parts)


def _parse_url(line: str) -> ParsedProxy:
    """Parse protocol://[user:pass@]host:port"""
    parsed = urlparse(line)
    protocol = parsed.scheme or "http"
    host = parsed.hostname or ""
    port = parsed.port or (1080 if protocol == "socks5" else 443 if protocol == "https" else 8080)
    return ParsedProxy(
        host=host, port=port, protocol=protocol,
        username=parsed.username or None,
        password=parsed.password or None,
    )


def _parse_ipv6_brackets(line: str) -> ParsedProxy:
    """Parse [ipv6]:port[@user:pass] or [ipv6]:port:user:pass"""
    bracket_end = line.index("]")
    host = line[1:bracket_end]
    rest = line[bracket_end + 1:]  # :port... or :port@user:pass
    if rest.startswith(":"):
        rest = rest[1:]
    if "@" in rest:
        port_str, auth = rest.split("@", 1)
        port = int(port_str)
        auth_parts = auth.split(":", 1)
        return ParsedProxy(
            host=host, port=port, protocol=_guess_protocol(port),
            username=auth_parts[0],
            password=auth_parts[1] if len(auth_parts) > 1 else None,
        )
    parts = rest.split(":")
    port = int(parts[0])
    return ParsedProxy(
        host=host, port=port, protocol=_guess_protocol(port),
        username=parts[1] if len(parts) > 1 else None,
        password=parts[2] if len(parts) > 2 else None,
    )


def _parse_delimited(parts: list[str]) -> ParsedProxy:
    """Parse space/tab/comma separated: host, port[, user, pass]"""
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) < 2 or not _is_port(parts[1]):
        raise ValueError(f"Unrecognized proxy format: {' '.join(parts)}")
    port = int(parts[1])
    return ParsedProxy(
        host=parts[0], port=port, protocol=_guess_protocol(port),
        username=parts[2] if len(parts) > 2 else None,
        password=parts[3] if len(parts) > 3 else None,
    )


def _parse_at_format(line: str) -> ParsedProxy:
    """Parse host:port@user:pass or user:pass@host:port"""
    left, right = line.split("@", 1)

    # Try right side as host:port (user:pass@host:port)
    right_parts = right.rsplit(":", 1)
    if len(right_parts) == 2 and _is_port(right_parts[1]) and _looks_like_host(right_parts[0]):
        port = int(right_parts[1])
        left_parts = left.split(":", 1)
        return ParsedProxy(
            host=right_parts[0], port=port, protocol=_guess_protocol(port),
            username=left_parts[0],
            password=left_parts[1] if len(left_parts) > 1 else None,
        )

    # Left side as host:port (host:port@user:pass)
    left_parts = left.rsplit(":", 1)
    if len(left_parts) == 2 and _is_port(left_parts[1]):
        port = int(left_parts[1])
        right_parts = right.split(":", 1)
        return ParsedProxy(
            host=left_parts[0], port=port, protocol=_guess_protocol(port),
            username=right_parts[0],
            password=right_parts[1] if len(right_parts) > 1 else None,
        )

    raise ValueError(f"Unrecognized proxy format: {line}")


def _parse_colon_parts(parts: list[str]) -> ParsedProxy:
    """Parse colon-separated: host:port, host:port:user:pass, user:pass:host:port, etc."""
    if len(parts) == 2:
        # host:port
        port = int(parts[1])
        return ParsedProxy(host=parts[0], port=port, protocol=_guess_protocol(port))

    if len(parts) >= 4:
        # Ambiguous: host:port:user:pass vs user:pass:host:port
        # Check parts[1] as port (host:port:user:pass)
        if _is_port(parts[1]) and _looks_like_host(parts[0]):
            port = int(parts[1])
            return ParsedProxy(
                host=parts[0], port=port, protocol=_guess_protocol(port),
                username=parts[2], password=parts[3],
            )
        # Check parts[3] as port (user:pass:host:port)
        if _is_port(parts[3]) and _looks_like_host(parts[2]):
            port = int(parts[3])
            return ParsedProxy(
                host=parts[2], port=port, protocol=_guess_protocol(port),
                username=parts[0], password=parts[1],
            )

    if len(parts) == 3:
        # host:port:protocol  (rare but some providers do this)
        if _is_port(parts[1]):
            port = int(parts[1])
            proto = parts[2].lower().strip()
            if proto in ("http", "https", "socks5", "socks4"):
                return ParsedProxy(host=parts[0], port=port, protocol=proto)
            # Might be host:port:user (no password)
            return ParsedProxy(
                host=parts[0], port=port, protocol=_guess_protocol(port),
                username=parts[2],
            )

    raise ValueError(f"Unrecognized proxy format: {':'.join(parts)}")
