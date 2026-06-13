# coding=utf-8
"""
Stock market identification and frequency utilities.
Ported from mootdx with enhancements.
"""

from pytdx.params import TDXParams

# K线周期名称映射
FREQUENCY = ['5m', '15m', '30m', '1h', 'days', 'week', 'mon', 'ex_1m', '1m', 'day', '3mon', 'year']


def get_stock_market(symbol=''):
    """根据股票代码自动判断市场

    ['50','51','60','68','90','110','113','132','204'] 为沪市
    ['00','12','13','18','15','16','20','30','39','115'] 为深市

    :param symbol: 股票代码
    :return: 市场代码 (0=深, 1=沪)
    """
    if not isinstance(symbol, str):
        symbol = str(symbol)

    if symbol.startswith(('sh', 'sz', 'SH', 'SZ')):
        return TDXParams.MARKET_SH if symbol[:2].lower() == 'sh' else TDXParams.MARKET_SZ

    if symbol.startswith(('50', '51', '60', '68', '90', '110', '113', '132', '204')):
        return TDXParams.MARKET_SH

    if symbol.startswith(('00', '12', '13', '18', '15', '16', '20', '30', '39', '115', '1318')):
        pass  # falls through to SZ below
        return TDXParams.MARKET_SZ

    if symbol.startswith(('5', '6', '9', '7')):
        return TDXParams.MARKET_SH

    # SH index: 88xxxx, 99xxxx
    if symbol.startswith(('88', '99')):
        return TDXParams.MARKET_SH

    return TDXParams.MARKET_SZ


def get_stock_markets(symbols=None):
    """批量获取股票市场列表

    :param symbols: 股票代码列表
    :return: [(market, code), ...]
    """
    results = []
    if isinstance(symbols, list):
        for symbol in symbols:
            code = symbol.lower().replace('sh', '').replace('sz', '')
            results.append((get_stock_market(symbol), code))
    return results


# 别名映射
FREQUENCY_ALIAS = {
    'month': 'mon', 'monthly': 'mon',
    'days': 'day', 'daily': 'day',
    'week': 'week', 'weekly': 'week',
    'year': 'year', 'yearly': 'year',
    'quarter': '3mon',
}


def get_frequency(frequency):
    """将K线周期名称转为数字索引

    :param frequency: 字符串如 '5m','day','week','month' 或数字 0-11
    :return: int
    """
    try:
        if isinstance(frequency, str):
            frequency = FREQUENCY_ALIAS.get(frequency, frequency)
            return FREQUENCY.index(frequency)
        return int(frequency)
    except (ValueError, IndexError):
        return 9  # default: 日K线
