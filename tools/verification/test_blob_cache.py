import os, sys, tempfile, io, shutil
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import calendar_worker as cw

CSV = b"BillNumber,HistoryDate,Committee\r\nHB1,01/01/2026,H01\r\nHB2,01/02/2026,H02\r\n"
URL = "https://lis.blob.core.windows.net/lisfiles/20261/HISTORY.CSV"

class FakeResp:
    def __init__(self, status, content=b"", etag=None, content_length=None):
        self.status_code = status
        self.content = content
        self.headers = {}
        if etag is not None:
            self.headers["ETag"] = etag
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

def install(queue):
    """Monkeypatch requests.get to pop scripted responses; capture sent headers."""
    sent = []
    def fake_get(url, timeout=None, headers=None):
        sent.append(headers or {})
        return queue.pop(0)
    cw.requests.get = fake_get
    return sent

def reset(tmp, enabled=True):
    cw._BLOB_CACHE_DIR = tmp
    cw._BLOB_CACHE_ENABLED = enabled
    cw.blob_cache_stats["reuse_304"] = 0
    cw.blob_cache_stats["download_200"] = 0

def main():
    tmp = tempfile.mkdtemp()
    fails = []

    # 1) cold: 200 download → DataFrame + cache write, no If-None-Match sent
    reset(tmp)
    sent = install([FakeResp(200, CSV, etag='"v1"', content_length=len(CSV))])
    df = cw.safe_fetch_csv(URL)
    if len(df) != 2: fails.append(f"1: expected 2 rows, got {len(df)}")
    if cw.blob_cache_stats["download_200"] != 1: fails.append("1: download_200 != 1")
    if "If-None-Match" in sent[0]: fails.append("1: should NOT send If-None-Match when cache cold")
    etag_read, body_read = cw._read_blob_cache(URL)
    if etag_read != '"v1"' or body_read != CSV: fails.append("1: cache not persisted correctly")

    # 2) warm: 304 → reuse cached bytes, If-None-Match sent, identical DataFrame
    reset(tmp)
    sent = install([FakeResp(304)])
    df2 = cw.safe_fetch_csv(URL)
    if len(df2) != 2: fails.append(f"2: expected 2 reused rows, got {len(df2)}")
    if cw.blob_cache_stats["reuse_304"] != 1: fails.append("2: reuse_304 != 1")
    if cw.blob_cache_stats["download_200"] != 0: fails.append("2: should not have downloaded")
    if sent[0].get("If-None-Match") != '"v1"': fails.append(f"2: wrong If-None-Match: {sent[0]}")
    if not df2.equals(df): fails.append("2: reused DataFrame differs from original (ACCURACY)")

    # 3) corrupt cache: 304 but cached bytes are junk → marker check fails → fall back to full GET
    reset(tmp)
    bin_path, _ = cw._blob_cache_paths(URL)
    with open(bin_path, "wb") as f:  # clobber cached bytes with junk of SAME length (defeat length check)
        f.write(b"x" * len(CSV))
    sent = install([FakeResp(304), FakeResp(200, CSV, etag='"v2"', content_length=len(CSV))])
    df3 = cw.safe_fetch_csv(URL)
    if len(df3) != 2: fails.append(f"3: expected fallback to 2 rows, got {len(df3)}")
    if cw.blob_cache_stats["download_200"] != 1: fails.append("3: should have fallen back to a download")
    if "If-None-Match" in sent[1]: fails.append("3: 2nd (fallback) attempt must be UNCONDITIONAL")

    # 4) kill switch: cache disabled → never sends If-None-Match, always downloads
    reset(tmp, enabled=False)
    sent = install([FakeResp(200, CSV, etag='"v3"', content_length=len(CSV))])
    df4 = cw.safe_fetch_csv(URL)
    if len(df4) != 2: fails.append(f"4: expected 2 rows, got {len(df4)}")
    if "If-None-Match" in sent[0]: fails.append("4: disabled cache must not send If-None-Match")

    # 5) length-mismatch in cache → read_blob_cache treats as miss
    reset(tmp)
    install([FakeResp(200, CSV, etag='"v4"', content_length=len(CSV))])
    cw.safe_fetch_csv(URL)  # repopulate cache
    bin_path, _ = cw._blob_cache_paths(URL)
    with open(bin_path, "ab") as f:
        f.write(b"EXTRA")  # now bytes longer than recorded length
    etag_read, body_read = cw._read_blob_cache(URL)
    if etag_read is not None: fails.append("5: length-mismatched cache should read as miss")

    if fails:
        shutil.rmtree(tmp, ignore_errors=True)
        print("❌ FAILURES:")
        for x in fails: print("   -", x)
        sys.exit(1)
    shutil.rmtree(tmp, ignore_errors=True)   # clean up the temp cache dir (Gemini #153 r2)
    print("✅ all blob-cache tests passed (200-write, 304-reuse, corrupt-fallback, kill-switch, length-guard)")

main()
