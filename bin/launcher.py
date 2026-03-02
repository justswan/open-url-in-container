#!/usr/bin/env python3
# Opens a URL in a specific Firefox container with HMAC-SHA256 signature.
#
# Environment variables:
#   OPEN_URL_IN_CONTAINER_SIGNING_KEY  - signing key (hex string, required)
#   OPEN_URL_IN_CONTAINER_EXT_UUID     - extension UUID (required for --print)
#   FIREFOX_BUNDLE_ID                  - macOS bundle ID (default: org.mozilla.nightly)

import argparse
import hmac
import hashlib
import os
import subprocess
import sys
import urllib.parse


def normalize_url(url: str) -> str:
    """Normalize URL to match JS new URL(url).toString() behavior."""
    parsed = urllib.parse.urlparse(url)
    if not parsed.path:
        parsed = parsed._replace(path="/")
    return urllib.parse.urlunparse(parsed)


def js_urlencode(params: list[tuple[str, str]]) -> str:
    """Encode params matching JS URLSearchParams.toString()."""
    def js_quote(s):
        encoded = urllib.parse.quote(s, safe="*-._")
        return encoded.replace("~", "%7E").replace(" ", "+")

    return "&".join(f"{js_quote(k)}={js_quote(v)}" for k, v in params)


def sign(container: str, url: str, key_hex: str) -> tuple[str, str]:
    """Build sorted query string and compute HMAC-SHA256, matching the extension."""
    normalized_url = normalize_url(url)
    params = sorted({"name": container, "url": normalized_url}.items())
    qs = js_urlencode(params)
    signature = hmac.new(
        bytes.fromhex(key_hex), qs.encode(), hashlib.sha256
    ).hexdigest()
    return qs, signature


def main():
    parser = argparse.ArgumentParser(
        description="Open URL in a Firefox container with signature."
    )
    parser.add_argument("-n", "--name", required=True, help="Container name")
    parser.add_argument("-p", "--print", action="store_true", dest="print_only",
                        help="Print a bookmark URL instead of opening Firefox")
    parser.add_argument("url", help="URL to open")
    args = parser.parse_args()

    key = os.environ.get("OPEN_URL_IN_CONTAINER_SIGNING_KEY", "")
    if not key:
        print("Error: OPEN_URL_IN_CONTAINER_SIGNING_KEY is not set", file=sys.stderr)
        sys.exit(1)

    qs, signature = sign(args.name, args.url, key)
    container_url = f"ext+container:{qs}&signature={signature}"

    if args.print_only:
        ext_uuid = os.environ.get("OPEN_URL_IN_CONTAINER_EXT_UUID", "")
        if not ext_uuid:
            print("Error: OPEN_URL_IN_CONTAINER_EXT_UUID is not set", file=sys.stderr)
            print("Find it in about:debugging → Extensions → Internal UUID", file=sys.stderr)
            sys.exit(1)
        encoded_hash = urllib.parse.quote(container_url, safe="")
        print(f"moz-extension://{ext_uuid}/opener.html#{encoded_hash}")
    else:
        bundle_id = os.environ.get("FIREFOX_BUNDLE_ID", "org.mozilla.nightly")
        subprocess.Popen(["open", "-b", bundle_id, container_url])


if __name__ == "__main__":
    main()
