# coding=utf-8
"""
前复权/后复权计算模块
"""

import pandas as pd


def to_adjust(df, symbol='', adjust='qfq'):
    """对K线数据做前复权或后复权

    :param df: 包含 open/high/low/close/volume 列的 DataFrame
    :param symbol: 股票代码
    :param adjust: 'qfq' 前复权, 'hfq' 后复权
    :return: pd.DataFrame
    """
    if df is None or df.empty:
        return df

    from pytdx.hq import TdxHq_API
    from pytdx.util.market import get_stock_market

    market = get_stock_market(symbol)
    api = TdxHq_API()

    try:
        with api.connect('218.75.126.9', 7709, time_out=5):
            xdxr = api.get_xdxr_info(market, symbol)
    except Exception:
        return df

    if not xdxr:
        return df

    xdxr_df = pd.DataFrame(xdxr)

    # 只取除权除息记录 (category=1)
    if 'category' in xdxr_df.columns:
        xdxr_df = xdxr_df[xdxr_df['category'] == 1]

    if xdxr_df.empty:
        return df

    # 计算复权因子
    factor = 1.0
    factors = []

    if adjust == 'qfq':
        # 前复权：从最早到最新
        for _, row in xdxr_df.iterrows():
            songzhuangu = row.get('songzhuangu') or 0
            peigu = row.get('peigu') or 0
            peigujia = row.get('peigujia') or 0
            fenhong = row.get('fenhong') or 0

            if peigujia == 0:
                peigujia = 1

            factor = factor * 10 / (10 + songzhuangu + peigu) * peigujia / (peigujia - fenhong / 10)
            factors.append(factor)

        if factors:
            final_factor = factors[-1]
    elif adjust == 'hfq':
        # 后复权：从最新到最早
        for _, row in xdxr_df.iterrows():
            songzhuangu = row.get('songzhuangu') or 0
            peigu = row.get('peigu') or 0
            peigujia = row.get('peigujia') or 0
            fenhong = row.get('fenhong') or 0

            if peigujia == 0:
                peigujia = 1

            factor = factor * (10 + songzhuangu + peigu) / 10 * (peigujia - fenhong / 10) / peigujia
            factors.append(factor)

        if factors:
            final_factor = factors[-1]

    if not factors:
        return df

    # 应用复权因子
    price_cols = ['open', 'high', 'low', 'close']
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col].astype(float) * final_factor

    return df
