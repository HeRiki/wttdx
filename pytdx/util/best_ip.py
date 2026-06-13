# coding=utf-8
"""
服务器测速模块 - 测试所有可用服务器并返回最快的
"""

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pytdx.config.hosts import hq_hosts
from pytdx.log import log

# 额外的服务器列表 (来自 mootdx)
EXTRA_HOSTS = [
    ('深圳双线主站1', '110.41.147.114', 7709),
    ('深圳双线主站2', '8.129.13.54', 7709),
    ('上海双线主站1', '124.70.176.52', 7709),
    ('上海双线主站2', '47.100.236.28', 7709),
    ('北京双线主站1', '121.36.54.217', 7709),
    ('广州双线主站1', '124.71.85.110', 7709),
]


def _test_connect(host):
    """测试单个服务器的连接速度"""
    name, ip, port = host
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        start = time.perf_counter()
        sock.connect((ip, int(port)))
        elapsed = (time.perf_counter() - start) * 1000  # ms
        sock.close()
        return (name, ip, port, elapsed)
    except Exception:
        return None


def select_best_ip(limit=5, verbose=True, extra=True):
    """多线程测速，返回最快的服务器

    :param limit: 返回前N个最快服务器
    :param verbose: 是否打印结果
    :param extra: 是否包含额外服务器
    :return: [(name, ip, port, ms), ...]
    """
    hosts = list(hq_hosts)
    if extra:
        hosts.extend(EXTRA_HOSTS)

    results = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_test_connect, h): h for h in hosts}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    results.sort(key=lambda x: x[3])
    results = results[:limit]

    if verbose:
        print(f"\n{'='*55}")
        print(f"  {'Name':<25} {'Addr':<18} {'Port':<6} {'Time':>8}")
        print(f"{'='*55}")
        for name, ip, port, ms in results:
            print(f"  {name:<25} {ip:<18} {port:<6} {ms:>7.2f}ms")
        print(f"{'='*55}")

    return results


def select_best_ip_simple(limit=1):
    """返回最快的服务器 IP 和端口

    :return: (ip, port) 或 None
    """
    results = select_best_ip(limit=limit, verbose=False)
    if results:
        return (results[0][1], results[0][2])
    return None
