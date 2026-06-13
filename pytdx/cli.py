# coding=utf-8
"""CLI command line tool. Usage: python -m pytdx [command]"""

import click


@click.group()
def cli():
    """pytdx - TDX data interface CLI tool"""
    pass


@cli.command()
@click.option('--limit', '-l', default=5, help='Return top N fastest servers')
def bestip(limit):
    """Test server speed and show the fastest ones"""
    from pytdx.util.best_ip import select_best_ip
    select_best_ip(limit=limit, verbose=True)


@cli.command()
@click.argument('symbol')
@click.option('--frequency', '-f', default='day', help='K-line frequency (day/1m/5m/week)')
@click.option('--offset', '-n', default=10, help='Number of bars')
@click.option('--output', '-o', default=None, help='Output file (csv/xlsx/json)')
def bars(symbol, frequency, offset, output):
    """Get K-line data. Example: pytdx bars 000001 -f day -n 10"""
    from pytdx.quotes import StdQuotes
    from pytdx.util.dataframe import to_file

    with StdQuotes() as q:
        df = q.bars(symbol=symbol, frequency=frequency, offset=offset)
        click.echo(df.to_string())
        if output:
            to_file(df, output)
            click.echo(f'\nSaved to {output}')


@cli.command()
@click.argument('symbol')
@click.option('--begin', '-b', default=None, help='Start date (e.g. 2020-01-01)')
@click.option('--end', '-e', default=None, help='End date')
@click.option('--adjust', '-a', default=None, help='Adjust: qfq/hfq')
@click.option('--output', '-o', default=None, help='Output file')
def k(symbol, begin, end, adjust, output):
    """Get K-line with date range and adjust. Example: pytdx k 000001 -b 2020-01-01 -e 2020-12-31 -a qfq -o data.csv"""
    from pytdx.quotes import StdQuotes
    from pytdx.util.dataframe import to_file
    from datetime import datetime

    if not begin:
        begin = '2020-01-01'
    if not end:
        end = datetime.now().strftime('%Y-%m-%d')

    kwargs = {}
    if adjust:
        kwargs['adjust'] = adjust

    with StdQuotes() as q:
        df = q.k(symbol=symbol, begin=begin, end=end, **kwargs)
        click.echo(df.to_string())
        if output:
            to_file(df, output)
            click.echo(f'\nSaved to {output}')


@cli.command()
@click.argument('symbol')
def quote(symbol):
    """Get real-time quote. Example: pytdx quote 000001"""
    from pytdx.quotes import StdQuotes
    with StdQuotes() as q:
        df = q.quotes(symbol=symbol)
        click.echo(df.to_string())


@cli.command()
@click.option('--market', '-m', default=0, type=click.Choice(['0', '1']), help='0=SZ 1=SH')
@click.option('--output', '-o', default=None, help='Output file')
def stocks(market, output):
    """Get stock list. Example: pytdx stocks -m 0"""
    from pytdx.quotes import StdQuotes
    from pytdx.util.dataframe import to_file
    with StdQuotes() as q:
        df = q.stocks(market=int(market))
        click.echo(df.to_string())
        if output:
            to_file(df, output)
            click.echo(f'\nSaved to {output}')


@cli.command()
@click.argument('symbol')
def xdxr(symbol):
    """Get ex-rights info. Example: pytdx xdxr 000001"""
    from pytdx.quotes import StdQuotes
    with StdQuotes() as q:
        df = q.xdxr(symbol=symbol)
        click.echo(df.to_string())


@cli.command()
@click.argument('symbol')
def finance(symbol):
    """Get financial info. Example: pytdx finance 000001"""
    from pytdx.quotes import StdQuotes
    with StdQuotes() as q:
        result = q.finance(symbol=symbol)
        click.echo(result)


def main():
    cli()


if __name__ == '__main__':
    main()
