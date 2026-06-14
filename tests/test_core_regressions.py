import hashlib
import io
import os
import stat
import struct
import subprocess
import sys
import zipfile

import pandas as pd
import pytest

from pytdx.bin import get_tdx_trader_server
from pytdx.crawler.history_financial_crawler import (
    HistoryFinancialCrawler,
    safe_extract_zip as crawler_safe_extract_zip,
)
from pytdx.exhq import TdxExHq_API
from pytdx.hq import TdxHq_API
from pytdx.parser.base import BaseParser
from pytdx.parser.ex_get_history_instrument_bars_range import GetHistoryInstrumentBarsRange
from pytdx.parser.ex_get_instrument_quote_list import GetInstrumentQuoteList
from pytdx.parser.get_history_minute_time_data import GetHistoryMinuteTimeData
from pytdx.parser.get_history_transaction_data import GetHistoryTransactionData
from pytdx.pool.hqpool import (
    TdxHqApiCallMaxRetryTimesReachedException,
    TdxHqPool_API,
)
from pytdx.quotes import StdQuotes


class FakeSocket:
    def __init__(self, response):
        self.response = bytearray(response)
        self.sent = bytearray()
        self.send_pkg_num = 0
        self.recv_pkg_num = 0
        self.send_pkg_bytes = 0
        self.recv_pkg_bytes = 0
        self.first_pkg_send_time = None
        self.last_api_send_bytes = 0
        self.last_api_recv_bytes = 0

    def sendall(self, data):
        self.sent.extend(data)

    def recv(self, size):
        if not self.response:
            return b""
        chunk_size = min(size, 3, len(self.response))
        chunk = self.response[:chunk_size]
        del self.response[:chunk_size]
        return bytes(chunk)


class EchoParser(BaseParser):
    def setup(self):
        self.send_pkg = b"request"

    def parseResponse(self, body_buf):
        return bytes(body_buf)


def test_base_parser_uses_sendall_and_reads_exact_response():
    body = b"abcde"
    header = struct.pack("<IIIHH", 0, 0, 0, len(body), len(body))
    sock = FakeSocket(header + body)

    assert EchoParser(sock).call_api() == body
    assert sock.sent == b"request"
    assert sock.send_pkg_bytes == len(b"request")
    assert sock.recv_pkg_bytes == len(header) + len(body)
    assert sock.last_api_recv_bytes == len(header) + len(body)


def test_get_report_file_by_size_does_not_prepend_zero_bytes():
    api = TdxHq_API()
    responses = [
        {"chunksize": 2, "chunkdata": b"ab"},
        {"chunksize": 2, "chunkdata": b"cd"},
    ]
    offsets = []

    def fake_get_report_file(filename, offset):
        offsets.append(offset)
        return responses.pop(0)

    api.get_report_file = fake_get_report_file
    assert api.get_report_file_by_size("x.dat", filesize=3) == bytearray(b"abc")
    assert offsets == [0, 2]


def test_history_transaction_date_accepts_string_and_bytes():
    parser = GetHistoryTransactionData(None)
    parser.setParams(0, "000001", 0, 10, "20170209")
    packed = parser.send_pkg[12:12 + struct.calcsize("<IH6sHH")]
    assert struct.unpack("<IH6sHH", packed)[0] == 20170209

    parser.setParams(0, "000001", 0, 10, b"20170209")
    packed = parser.send_pkg[12:12 + struct.calcsize("<IH6sHH")]
    assert struct.unpack("<IH6sHH", packed)[0] == 20170209


def test_history_minute_date_accepts_string_and_bytes():
    parser = GetHistoryMinuteTimeData(None)
    parser.setParams(0, "000001", "20161209")
    packed = parser.send_pkg[12:12 + struct.calcsize("<IB6s")]
    assert struct.unpack("<IB6s", packed)[0] == 20161209

    parser.setParams(0, "000001", b"20161209")
    packed = parser.send_pkg[12:12 + struct.calcsize("<IB6s")]
    assert struct.unpack("<IB6s", packed)[0] == 20161209


class FakeQuotesClient:
    def __init__(self):
        self.calls = []

    def get_security_bars(self, category, market, code, start, count):
        self.calls.append((category, market, code, start, count))
        rows = {
            800: [{"datetime": "2020-01-02 15:00", "open": 1, "close": 2}],
            0: [{"datetime": "2020-01-03 15:00", "open": 2, "close": 3}],
        }
        return rows.get(start, [])

    def to_df(self, result):
        return pd.DataFrame(result)


def test_std_quotes_get_k_data_returns_filtered_dataframe():
    quotes = object.__new__(StdQuotes)
    quotes.client = FakeQuotesClient()

    df = quotes.get_k_data("000001", "2020-01-02", "2020-01-03")

    assert list(df.index) == ["2020-01-02", "2020-01-03"]
    assert list(df["code"]) == ["000001", "000001"]
    assert len(quotes.client.calls) == 10


class NoneQuotesClient:
    def get_security_bars(self, *args):
        return None

    def to_df(self, result):
        raise AssertionError("to_df should not be called for empty api results")


def test_std_quotes_get_k_data_skips_failed_api_results():
    quotes = object.__new__(StdQuotes)
    quotes.client = NoneQuotesClient()

    df = quotes.get_k_data("000001", "2020-01-02", "2020-01-03")

    assert df.empty


class AlwaysNoneApi:
    def __init__(self, *args, **kwargs):
        self.ip = None

    def get_data(self):
        return None

    def connect(self, ip, port):
        self.ip = ip
        return self

    def disconnect(self):
        pass


class FakeIpPool:
    def __init__(self):
        self.index = 0
        self.teardown_called = False

    def get_ips(self):
        self.index += 1
        return [
            ("127.0.0.%d" % self.index, 7709),
            ("127.0.1.%d" % self.index, 7709),
        ]

    def teardown(self):
        self.teardown_called = True


def test_hq_pool_retry_stops_at_configured_limit():
    api = TdxHqPool_API(AlwaysNoneApi, FakeIpPool())
    api.api_retry_interval = 0
    api.api_call_max_retry_times = 2

    with pytest.raises(TdxHqApiCallMaxRetryTimesReachedException):
        api.get_data()

    assert api.api_call_retry_times == 2


class EmptyIpPool(FakeIpPool):
    def get_ips(self):
        return []


def test_hq_pool_disconnect_handles_missing_hot_failover():
    ippool = EmptyIpPool()
    api = TdxHqPool_API(AlwaysNoneApi, ippool)
    api.api_retry_interval = 0
    api.api_call_max_retry_times = 1

    with pytest.raises(TdxHqApiCallMaxRetryTimesReachedException):
        api.get_data()

    assert api.hot_failover_api is None
    api.disconnect()
    assert ippool.teardown_called


def test_exhq_methods_pass_shared_lock_to_parsers(monkeypatch):
    seen_locks = []

    class ParserStub:
        def __init__(self, client, lock=None):
            seen_locks.append(lock)

        def setParams(self, *args, **kwargs):
            pass

        def call_api(self):
            return []

    monkeypatch.setattr("pytdx.exhq.GetMarkets", ParserStub)
    monkeypatch.setattr("pytdx.exhq.GetInstrumentQuote", ParserStub)

    api = TdxExHq_API(multithread=True)
    api.client = object()

    api.get_markets()
    api.get_instrument_quote(47, "IF1709")

    assert seen_locks == [api.lock, api.lock]


def test_history_instrument_bars_range_does_not_print_count(capsys):
    parser = GetHistoryInstrumentBarsRange(None)
    body = b"\x00" * 12 + struct.pack("<H", 0)

    assert parser.parseResponse(body) == []
    assert capsys.readouterr().out == ""


def test_instrument_quote_list_unsupported_category_raises():
    parser = GetInstrumentQuoteList(None)
    parser.category = 1

    with pytest.raises(NotImplementedError):
        parser.parseResponse(struct.pack("<H", 1))


def make_financial_dat():
    header_format = "<1hI1H3L"
    item_format = "<6s1c1L"
    header_size = struct.calcsize(header_format)
    item_size = struct.calcsize(item_format)
    data_offset = header_size + item_size
    header = struct.pack(header_format, 0, 20200101, 1, 0, 4, 0)
    item = struct.pack(item_format, b"000001", b"\0", data_offset)
    return header + item + struct.pack("<f", 1.25)


def test_history_financial_crawler_uses_filename_hint_for_zip(tmp_path):
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("gpcw.dat", make_financial_dat())
    zip_bytes.seek(0)

    no_suffix_file = tmp_path / "download.tmp"
    no_suffix_file.write_bytes(zip_bytes.read())

    with no_suffix_file.open("rb") as f:
        rows = HistoryFinancialCrawler().parse(f, filename="gpcw20200101.zip")

    assert rows == [("000001", 20200101, 1.25)]


def test_history_financial_crawler_cleans_tmpdir_on_parse_error(monkeypatch, tmp_path):
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("not-a-dat.txt", b"x")
    zip_bytes.seek(0)

    no_suffix_file = tmp_path / "download.tmp"
    no_suffix_file.write_bytes(zip_bytes.read())
    created_dirs = []

    def fake_gettempdir():
        return str(tmp_path)

    def fake_randint(start, end):
        return 12345

    monkeypatch.setattr("pytdx.crawler.history_financial_crawler.tempfile.gettempdir", fake_gettempdir)
    monkeypatch.setattr("pytdx.crawler.history_financial_crawler.random.randint", fake_randint)

    with no_suffix_file.open("rb") as f:
        with pytest.raises(Exception, match="no dat file found"):
            HistoryFinancialCrawler().parse(f, filename="gpcw20200101.zip")

    created_dirs.append(tmp_path / "pytdx_12345")
    assert all(not path.exists() for path in created_dirs)


def test_crawler_safe_extract_zip_rejects_path_traversal(tmp_path):
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("../evil.dat", b"x")
    zip_bytes.seek(0)

    with zipfile.ZipFile(zip_bytes) as zf:
        with pytest.raises(Exception, match="unsafe zip path"):
            crawler_safe_extract_zip(zf, str(tmp_path))


def test_crawler_safe_extract_zip_rejects_symlink(tmp_path):
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        info = zipfile.ZipInfo("link.dat")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "target.dat")
    zip_bytes.seek(0)

    with zipfile.ZipFile(zip_bytes) as zf:
        with pytest.raises(Exception, match="unsafe zip symlink"):
            crawler_safe_extract_zip(zf, str(tmp_path))


def test_trade_installer_safe_extract_zip_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.dll", b"x")

    with pytest.raises(SystemExit, match="拒绝解压越界路径"):
        get_tdx_trader_server.safe_extract_zip(str(zip_path), str(tmp_path / "out"))


def test_trade_installer_safe_extract_zip_rejects_symlink(tmp_path):
    zip_path = tmp_path / "bad-link.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        info = zipfile.ZipInfo("link.dll")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "target.dll")

    with pytest.raises(SystemExit, match="拒绝解压符号链接"):
        get_tdx_trader_server.safe_extract_zip(str(zip_path), str(tmp_path / "out"))


def test_secure_download_requires_https_and_validates_sha(monkeypatch, tmp_path):
    output = tmp_path / "Trade.dll"

    with pytest.raises(SystemExit, match="下载地址为空"):
        get_tdx_trader_server.secure_download(None, str(output), "abc")

    with pytest.raises(SystemExit, match="下载地址必须是 HTTP 或 HTTPS"):
        get_tdx_trader_server.secure_download("ftp://example.com/Trade.dll", str(output), "abc")

    def fake_urlretrieve(url, output_path):
        with open(output_path, "wb") as f:
            f.write(b"trade")

    monkeypatch.setattr(get_tdx_trader_server, "urlretrieve", fake_urlretrieve)
    get_tdx_trader_server.secure_download("http://example.com/Trade.dll", str(output))
    assert output.read_bytes() == b"trade"

    expected = hashlib.sha256(b"trade").hexdigest()
    get_tdx_trader_server.secure_download("https://example.com/Trade.dll", str(output), expected)

    assert output.read_bytes() == b"trade"


def test_trade_installer_module_reports_invalid_download_url():
    env = os.environ.copy()
    env["PYTDX_TRADE_DLL_URL"] = "ftp://example.com/Trade.dll"
    result = subprocess.run(
        [sys.executable, "-m", "pytdx.bin.get_tdx_trader_server"],
        input="y\n",
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    assert "下载地址必须是 HTTP 或 HTTPS" in result.stderr
