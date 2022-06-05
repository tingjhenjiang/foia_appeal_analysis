import scrapy,json,six,re,time
import scrapycrawler.spiders.req as req
import pandas as pd
import tabula
from pdfminer.high_level import extract_pages as pdfminerExtractPages
from pdfminer.layout import LTTextContainer as pdfminerLTTextContainer
import logging,time
from os.path import exists
import threading, queue

logging.getLogger("pdfminer").setLevel(logging.WARNING)

class MOFASpider(scrapy.spiders.CrawlSpider):
    name = 'mofa'
    custom_settings = {
        'ROBOTSTXT_OBEY':False,
        'CONCURRENT_ITEMS':5,
        'CONCURRENT_REQUESTS':5,
        'CONCURRENT_REQUESTS_PER_DOMAIN':5,
        'DEPTH_LIMIT':999999999999999999999999,
        }
    start_urls = ['https://www.mofa.gov.tw/News.aspx?n=1013&sms=229']

    def parse_start_url(self, response):
        self.logger.info('A response from start_url %s just arrived!', response.url)
        self.mofadeisionlist = {
            'link':response.xpath('//tr[position()>=1]/td[contains(@class,"CCMS_jGridView_td_Class_0")]/span/a/@href').getall(),
            'caseid':response.xpath('//tr[position()>=1]/td[contains(@class,"CCMS_jGridView_td_Class_0")]/span/a/text()').getall(),
        }
        self.logger.info(self.mofadeisionlist)
        for itemi,link in enumerate(self.mofadeisionlist['link']):
            decisionData = {
                'DCS_FILEID':self.mofadeisionlist['caseid'][itemi],
                'link':link
                }
            textinfo = req.parse_text_file(decisionData)
            textinfo = req.parse_with_regexp_on_whole_str("\n".join(textinfo))
            decisionData = {**decisionData, **textinfo}
            yield(decisionData)
            self.logger.info(decisionData)
        if False:
            yield response.follow(link, callback=self.parse_single_decision_page, meta={'meta':self.moideisionlist[link]})
