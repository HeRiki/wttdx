# coding=utf-8
"""
DataFrame conversion and export utilities.
"""

from pathlib import Path

import pandas as pd
from pandas import DataFrame


def to_data(v, **kwargs):
    """将返回值统一转换为 DataFrame，支持复权

    :param v: 原始返回值 (list / dict / DataFrame / None)
    :param kwargs: symbol, adjust
    :return: pd.DataFrame
    """
    symbol = kwargs.get('symbol')
    adjust = kwargs.get('adjust', '').lower()

    if adjust in ('01', 'qfq', 'before'):
        adjust = 'qfq'
    elif adjust in ('02', 'hfq', 'after'):
        adjust = 'hfq'
    else:
        adjust = None

    if not isinstance(v, DataFrame) and not v:
        return pd.DataFrame(data=None)

    if isinstance(v, DataFrame):
        result = v
    elif isinstance(v, list):
        result = pd.DataFrame(data=v) if len(v) else pd.DataFrame(data=None)
    elif isinstance(v, dict):
        result = pd.DataFrame(data=[v])
    else:
        result = pd.DataFrame(data=[])

    if 'datetime' in result.columns:
        result.index = pd.to_datetime(result.datetime)
    if 'date' in result.columns:
        result.index = pd.to_datetime(result.date)
    if 'vol' in result.columns:
        result['volume'] = result.vol

    if adjust and symbol:
        from pytdx.util.adjust import to_adjust
        result = to_adjust(result, symbol=symbol, adjust=adjust)

    return result


def to_file(df, filename=None):
    """DataFrame 导出为文件（支持 csv/xlsx/json/h5）

    :param df: pd.DataFrame
    :param filename: 文件路径
    :return: bool or None
    """
    if filename is None or df is None:
        return None

    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    ext = path.suffix.lower()
    if ext == '.csv':
        df.to_csv(filename, encoding='utf-8-sig', index=False)
    elif ext in ('.xlsx', '.xls'):
        df.to_excel(filename, index=False)
    elif ext == '.h5':
        df.to_hdf(filename, 'df', index=False)
    elif ext == '.json':
        df.to_json(filename, orient='records', force_ascii=False)
    else:
        return None
    return True
