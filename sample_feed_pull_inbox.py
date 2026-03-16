#!/usr/bin/env python3
"""
Sample script: TAXII 2.1 feed Pull and Inbox using cytaxii2.

- User selects action: Pull (get objects from a collection) or Inbox (post a STIX bundle).
- Downloaded feed is saved as: {collection_id}_{timestamp}.json
- Uses STIX 2.1 / TAXII 2.1.
- Script options #3 & #4 are used to test rate limiting. Configure TAXII server 
  limit to 10 requests per minut.
"""

import json
import os
import sys
from datetime import datetime, timezone

# -----------------------------------------------------------------------------
# Placeholders — set these before running
# -----------------------------------------------------------------------------
DISCOVERY_URL = ""  # TAXII 2.1 Discovery URL
USERNAME = ""       # Basic auth username
PASSWORD = ""       # Basic auth password
# -----------------------------------------------------------------------------

# Optional: directory where to save pulled feeds (default: current directory)
OUTPUT_DIR = "."

# Set to 1 to print full server response (status, status_code, response) after each request; 0 to skip (STIX output is long).
DEBUG = 0


def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def safe_feed_id(collection_id):
    """Make collection_id safe for use in a filename."""
    if not collection_id:
        return "feed"
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in collection_id)


def print_response_headers(label, result):
    """Print response headers (e.g. Retry-After, rate limit info). Used in regular mode."""
    headers = result.get("headers")
    if not headers:
        return
    print("\n--- {} (headers) ---".format(label))
    for k, v in sorted(headers.items()):
        print("  {}: {}".format(k, v))
    print("---\n")


def print_server_response(label, result):
    """Always print the full server response (status, status_code, headers, response) for debugging."""
    print("\n--- {} ---".format(label))
    print("status: {}".format(result.get("status")))
    print("status_code: {}".format(result.get("status_code")))
    headers = result.get("headers")
    if headers:
        print("headers:")
        for k, v in sorted(headers.items()):
            print("  {}: {}".format(k, v))
    resp = result.get("response")
    if isinstance(resp, (dict, list)):
        print("response:\n{}".format(json.dumps(resp, indent=2)))
    else:
        print("response: {}".format(resp))
    print("---\n")


def main():
    # Use lib from this repo first (no install needed after git clone), then installed
    _project_root = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(0, _project_root)
    try:
        from cytaxii2.cytaxii2 import cytaxii2
    except ImportError as e:
        err = str(e)
        if "requests" in err or "No module named" in err:
            print("Missing dependency. From repo root: pip install -r requirements.txt", file=sys.stderr)
        else:
            print("cytaxii2 not found. Run from repo root or install: pip install -e .", file=sys.stderr)
        print("  ({})".format(e), file=sys.stderr)
        sys.exit(1)

    client = cytaxii2(
        discovery_url=DISCOVERY_URL,
        username=USERNAME,
        password=PASSWORD,
        version=2.1,
    )

    # Discovery: get API root and list collections
    print("Performing discovery...")
    collections_resp = client.collection_request()
    if DEBUG:
        print_server_response("collection_request", collections_resp)
    else:
        print_response_headers("collection_request", collections_resp)
    if not collections_resp.get("status"):
        r = collections_resp.get("response") or {}
        msg = r.get("error", r) if isinstance(r, dict) else r
        print("Failed to get collections (status_code={}): {}".format(
            collections_resp.get("status_code"), msg), file=sys.stderr)
        sys.exit(1)

    collections = (collections_resp.get("response") or {}).get("collections", [])
    if not collections:
        print("No collections found.")
        sys.exit(1)

    print("\nAvailable collections:")
    for i, col in enumerate(collections, 1):
        print("  {}: {} (id: {})".format(i, col.get("title", "—"), col.get("id", "—")))

    sel = input("Select collection (enter number or collection id): ").strip()
    collection_id = None
    for i, c in enumerate(collections, 1):
        if c.get("id") == sel or sel == str(i):
            collection_id = c.get("id")
            break
    if not collection_id and sel:
        collection_id = sel  # user typed an id that wasn't in the list
    elif not collection_id:
        collection_id = collections[0].get("id")

    print("\nTAXII 2.1 – Pull / Inbox (STIX 2.1)")
    print("1) Pull  – get objects from this collection (save to file)")
    print("2) Inbox – post a STIX 2.1 bundle to this collection")
    print("3) Loop  – 15 poll requests (no save)")
    print("4) Loop  – 15 inbox requests")
    choice = input("Select action (1–4): ").strip()

    if choice not in ("1", "2", "3", "4"):
        print("Invalid choice. Exiting.")
        sys.exit(1)

    if choice == "1":
        # --- Pull ---
        added_after = input("Optional added_after (ISO8601, or Enter to skip): ").strip() or None
        limit_str = input("Optional limit (or Enter to skip): ").strip()
        limit = int(limit_str) if limit_str.isdigit() else None

        poll_resp = client.poll_request(
            collection_id=collection_id,
            added_after=added_after,
            limit=limit,
        )
        if DEBUG:
            print_server_response("poll_request", poll_resp)
        else:
            print_response_headers("poll_request", poll_resp)
        if not poll_resp.get("status"):
            r = poll_resp.get("response") or {}
            msg = r.get("error", r) if isinstance(r, dict) else r
            print("Poll failed (status_code={}): {}".format(
                poll_resp.get("status_code"), msg), file=sys.stderr)
            sys.exit(1)

        filename = "{}_{}.json".format(safe_feed_id(collection_id), get_timestamp())
        out_path = os.path.join(OUTPUT_DIR, filename) if OUTPUT_DIR else filename
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        payload = poll_resp.get("response")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload if payload is not None else {}, f, indent=2)
        print("Saved pull response to:", out_path)

    elif choice == "2":
        # --- Inbox ---
        bundle_path = input("Path to STIX 2.1 bundle JSON file: ").strip()
        if not bundle_path:
            print("No file path given. Exiting.")
            sys.exit(1)
        try:
            with open(bundle_path, encoding="utf-8") as f:
                raw = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print("Failed to read bundle file {}: {}".format(bundle_path, e), file=sys.stderr)
            sys.exit(1)

        # Library POST uses data= for string or json= for dict
        inbox_resp = client.inbox_request(collection_id=collection_id, stix_bundle=raw)
        if DEBUG:
            print_server_response("inbox_request", inbox_resp)
        else:
            print_response_headers("inbox_request", inbox_resp)
        if not inbox_resp.get("status"):
            r = inbox_resp.get("response") or {}
            msg = r.get("error", r) if isinstance(r, dict) else r
            print("Inbox request failed (status_code={}): {}".format(
                inbox_resp.get("status_code"), msg), file=sys.stderr)
            sys.exit(1)
        payload = inbox_resp.get("response")
        print("Inbox response:", json.dumps(payload if payload is not None else {}, indent=2))

    elif choice == "3":
        # --- Loop: 15 poll requests ---
        for i in range(1, 16):
            poll_resp = client.poll_request(collection_id=collection_id)
            print("Poll request {}/15: status={}, status_code={}".format(
                i, poll_resp.get("status"), poll_resp.get("status_code")))
            if DEBUG:
                print_server_response("poll_request #{}".format(i), poll_resp)
            else:
                print_response_headers("poll_request #{}".format(i), poll_resp)
            if not poll_resp.get("status"):
                r = poll_resp.get("response") or {}
                msg = r.get("error", r) if isinstance(r, dict) else r
                print("Poll failed (status_code={}): {}".format(
                    poll_resp.get("status_code"), msg), file=sys.stderr)
        print("Done: 15 poll requests completed.")

    elif choice == "4":
        # --- Loop: 15 inbox requests ---
        bundle_path = input("Path to STIX 2.1 bundle JSON file: ").strip()
        if not bundle_path:
            print("No file path given. Exiting.")
            sys.exit(1)
        try:
            with open(bundle_path, encoding="utf-8") as f:
                raw = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print("Failed to read bundle file {}: {}".format(bundle_path, e), file=sys.stderr)
            sys.exit(1)
        for i in range(1, 16):
            inbox_resp = client.inbox_request(collection_id=collection_id, stix_bundle=raw)
            print("Inbox request {}/15: status={}, status_code={}".format(
                i, inbox_resp.get("status"), inbox_resp.get("status_code")))
            if DEBUG:
                print_server_response("inbox_request #{}".format(i), inbox_resp)
            else:
                print_response_headers("inbox_request #{}".format(i), inbox_resp)
            if not inbox_resp.get("status"):
                r = inbox_resp.get("response") or {}
                msg = r.get("error", r) if isinstance(r, dict) else r
                print("Inbox failed (status_code={}): {}".format(
                    inbox_resp.get("status_code"), msg), file=sys.stderr)
        print("Done: 15 inbox requests completed.")


if __name__ == "__main__":
    main()

