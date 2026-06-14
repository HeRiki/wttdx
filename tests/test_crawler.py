import os
import pytest
import pandas as pd
from pytdx.crawler.base_crawler import demo_reporthook
from pytdx.crawler.history_financial_crawler import HistoryFinancialListCrawler

pytestmark = pytest.mark.skipif(
    os.getenv("PYTDX_RUN_INTEGRATION") != "1",
    reason="set PYTDX_RUN_INTEGRATION=1 to run network integration tests",
)

def test_crawl_history_financial_list_via_tcp():

    crawler = HistoryFinancialListCrawler()
    
    list_data = crawler.fetch_and_parse(reporthook=demo_reporthook)
    df = pd.DataFrame(data=list_data)
    assert df["filename"].str.contains("gpcw20190630.zip").any()

def test_crawl_history_financial_list_via_http(): 
    # via yutianst's http server
    crawler = HistoryFinancialListCrawler()
    crawler.mode = "http"
    
    list_data = crawler.fetch_and_parse(reporthook=demo_reporthook)
    df = pd.DataFrame(data=list_data)
    assert df["filename"].str.contains("gpcw20190630.zip").any()
