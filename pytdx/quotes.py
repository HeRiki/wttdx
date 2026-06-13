# coding=utf-8
"""
高层行情接口 - 工厂模式
提供更友好的 API，自动市场识别、DataFrame 返回
"""

import math
from datetime import datetime

import pandas as pd

from pytdx.exhq import TdxExHq_API
from pytdx.hq import TdxHq_API
from pytdx.params import TDXParams
from pytdx.util.market import get_stock_market, get_stock_markets, get_frequency
from pytdx.util.dataframe import to_data
from pytdx.util.best_ip import select_best_ip_simple
from pytdx.log import log

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


class Quotes:
    """行情工厂"""

    @staticmethod
    def factory(market='std', **kwargs):
        """创建行情实例

        :param market: 'std' 标准市场, 'ext' 扩展市场
        :return: StdQuotes 或 ExtQuotes
        """
        if market == 'ext':
            return ExtQuotes(**kwargs)
        return StdQuotes(**kwargs)


class StdQuotes:
    """标准A股行情接口

    自动选择最快服务器，返回 DataFrame，支持复权。

    用法::

        quotes = StdQuotes()
        df = quotes.bars(symbol='000001', frequency='day')
        df = quotes.quotes(symbol=['000001', '600300'])
        df = quotes.k(symbol='000001', begin='2020-01-01', end='2020-12-31', adjust='qfq')
    """

    def __init__(self, server=None, bestip=False, timeout=15, heartbeat=False,
                 auto_retry=True, raise_exception=False, **kwargs):
        if server is None and bestip:
            server = select_best_ip_simple()

        if server is None:
            server = ('218.75.126.9', 7709)

        if isinstance(server, tuple):
            ip, port = server
        else:
            ip, port = server, 7709

        self.client = TdxHq_API(heartbeat=heartbeat, auto_retry=auto_retry,
                                raise_exception=raise_exception)
        self.client.connect(ip, int(port), time_out=timeout)

    def close(self):
        """断开连接"""
        if self.client:
            self.client.disconnect()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def quotes(self, symbol=None, **kwargs):
        """获取实时行情

        :param symbol: 股票代码或代码列表
        :return: pd.DataFrame
        """
        if not symbol:
            return to_data(None)

        if isinstance(symbol, str):
            symbol = [symbol]

        symbol = get_stock_markets(symbol)
        result = self.client.get_security_quotes(symbol)
        return to_data(result, symbol=symbol, **kwargs)

    def bars(self, symbol='000001', frequency=9, start=0, offset=800, **kwargs):
        """获取K线数据

        :param symbol: 股票代码
        :param frequency: K线周期 (int 或 str 如 'day','1m','5m')
        :param start: 起始位置
        :param offset: 获取条数 (最多800)
        :return: pd.DataFrame
        """
        frequency = get_frequency(frequency)
        market = get_stock_market(symbol)
        offset = min(offset, 800)
        result = self.client.get_security_bars(int(frequency), int(market),
                                                str(symbol), int(start), int(offset))
        return to_data(result, symbol=symbol, **kwargs)

    def index_bars(self, symbol='000001', frequency=9, start=0, offset=800, **kwargs):
        """获取指数K线

        :param symbol: 指数代码
        :param frequency: K线周期
        :param start: 起始位置
        :param offset: 获取条数
        :return: pd.DataFrame
        """
        frequency = get_frequency(frequency)
        market = get_stock_market(symbol)
        offset = min(offset, 800)
        result = self.client.get_index_bars(int(frequency), int(market),
                                             str(symbol), int(start), int(offset))
        return to_data(result, symbol=symbol, **kwargs)

    def stock_count(self, market=TDXParams.MARKET_SH):
        """获取市场股票数量"""
        return self.client.get_security_count(market=market)

    def stocks(self, market=TDXParams.MARKET_SH):
        """获取股票列表

        :param market: 市场代码 (0=深, 1=沪)
        :return: pd.DataFrame
        """
        counts = self.stock_count(market=market)
        stocks = None

        if counts > 0:
            range_iter = range(0, counts, 1000)
            if tqdm:
                range_iter = tqdm(range_iter, desc='Fetching stocks', ascii=True)

            for start in range_iter:
                result = self.client.get_security_list(market=market, start=start)
                df = to_data(result)
                stocks = pd.concat([stocks, df], ignore_index=True) if stocks is not None else df

        return stocks

    def stock_all(self):
        """获取沪深全部股票列表"""
        stocks = None
        for m in (TDXParams.MARKET_SZ, TDXParams.MARKET_SH):
            df = self.stocks(m)
            stocks = pd.concat([stocks, df], ignore_index=True) if stocks is not None else df
        return stocks

    def minute(self, symbol=None, **kwargs):
        """获取当日分时数据"""
        today = datetime.now().strftime('%Y%m%d')
        return self.minutes(symbol=symbol, date=today, **kwargs)

    def minutes(self, symbol=None, date='20191023', **kwargs):
        """获取历史分时数据

        :param symbol: 股票代码
        :param date: 日期 (如 20200101)
        :return: pd.DataFrame
        """
        market = get_stock_market(symbol)
        result = self.client.get_history_minute_time_data(market=market, code=symbol, date=date)
        return to_data(result, symbol=symbol, **kwargs)

    def transaction(self, symbol='', start=0, offset=800, **kwargs):
        """获取分笔成交"""
        market = get_stock_market(symbol)
        result = self.client.get_transaction_data(int(market), symbol, start, offset)
        return to_data(result, symbol=symbol, **kwargs)

    def transactions(self, symbol='', start=0, offset=800, date='20170209', **kwargs):
        """获取历史分笔成交"""
        market = get_stock_market(symbol)
        result = self.client.get_history_transaction_data(market, symbol, start, offset, int(date))
        return to_data(result, symbol=symbol, **kwargs)

    def xdxr(self, symbol='', **kwargs):
        """获取除权除息信息"""
        market = get_stock_market(symbol)
        result = self.client.get_xdxr_info(int(market), symbol)
        return to_data(result, symbol=symbol, **kwargs)

    def finance(self, symbol='000001', **kwargs):
        """获取财务信息"""
        market = get_stock_market(symbol)
        result = self.client.get_finance_info(market=market, code=symbol)
        return to_data(result, symbol=symbol, **kwargs)

    def F10(self, symbol='', name=''):
        """获取公司信息

        :param symbol: 股票代码
        :param name: F10 标题 (如为空返回全部)
        :return: dict 或 str
        """
        market = int(get_stock_market(symbol))
        category = self.client.get_company_info_category(market, symbol)
        if not category:
            return None

        if name:
            for x in category:
                if x['name'] == name:
                    return self.client.get_company_info_content(
                        market=market, code=symbol,
                        filename=x['filename'], start=x['start'], length=x['length'])

        result = {}
        for x in category:
            result[x['name']] = self.client.get_company_info_content(
                market=market, code=symbol,
                filename=x['filename'], start=x['start'], length=x['length'])
        return result

    def block(self, tofile='block.dat', **kwargs):
        """获取板块信息"""
        result = self.client.get_and_parse_block_info(tofile)
        return to_data(result, **kwargs)

    def k(self, symbol='', begin=None, end=None, **kwargs):
        """获取K线数据（支持日期范围）

        :param symbol: 股票代码
        :param begin: 开始日期
        :param end: 结束日期
        :return: pd.DataFrame
        """
        result = self.get_k_data(symbol, begin, end)
        return to_data(result, symbol=symbol, **kwargs)

    def get_k_data(self, code, start_date, end_date):
        """获取K线数据的底层实现"""
        first = (pd.to_datetime(end_date) - pd.to_datetime(datetime.now().date())).days
        first = (abs(first), 0)[first >= 0]

        last = (pd.to_datetime(start_date) - pd.to_datetime(datetime.now().date())).days
        last = (abs(last), 0)[last >= 0]

        first -= int(first / 2.8)
        last -= int(last / 3.5)

      


class ExtQuotes:
    """扩展市场行情接口"""

    def __init__(self, server=None, bestip=False, timeout=15, **kwargs):
        if server is None:
            server = ('112.74.214.43', 7727)

        if isinstance(server, tuple):
            ip, port = server
        else:
            ip, port = server, 7727

        self.client = TdxExHq_API(auto_retry=True)
        self.client.connect(ip, int(port), time_out=timeout)

    def close(self):
        if self.client:
            self.client.disconnect()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def markets(self, **kwargs):
        """获取市场列表"""
        result = self.client.get_markets()
        return to_data(result, **kwargs)

    def bars(self, frequency='', market='', symbol='', start=0, offset=800, **kwargs):
        """获取K线数据"""
        frequency = get_frequency(frequency)
        result = self.client.get_instrument_bars(
            category=frequency, market=market, code=symbol, start=start, count=offset)
        return to_data(result, symbol=symbol, **kwargs)

    def quote(self, market='', symbol='', **kwargs):
        """获取五档行情"""
        result = self.client.get_instrument_quote(market, symbol)
        return to_data(result, symbol=symbol, **kwargs)

    def instruments(self, **kwargs):
        """获取全部代码列表"""
        count = self.client.get_instrument_count()
        result = []
        pages = math.ceil(count / 100)

        range_iter = range(0, pages)
        if tqdm:
            range_iter = tqdm(range_iter, desc='Fetching instruments', ascii=True)

        for page in range_iter:
            result += self.client.get_instrument_info(page * 100, 100)

        return to_data(result, **kwargs)

    def transaction(self, market=None, symbol='', start=0, offset=800, **kwargs):
        """获取分笔成交"""
        result = self.client.get_transaction_data(market=market, code=symbol, start=start, count=offset)
        return to_data(result, symbol=symbol, **kwargs)
