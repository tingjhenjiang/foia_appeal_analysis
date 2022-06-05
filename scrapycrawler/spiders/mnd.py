import scrapy,json,six,re,time
import scrapycrawler.spiders.req as req
import pandas as pd
import logging,time
import lxml
from os.path import exists
import threading, queue

logging.getLogger("pdfminer").setLevel(logging.WARNING)

class MNDSpider(scrapy.spiders.CrawlSpider):
    name = 'mnd'
    custom_settings = {
        'ROBOTSTXT_OBEY':False,
        'CONCURRENT_ITEMS':2,
        'CONCURRENT_REQUESTS':2,
        'CONCURRENT_REQUESTS_PER_DOMAIN':2,
        'DEPTH_LIMIT':999999999999999999999999,
        }
    start_urls = ['https://law.mnd.gov.tw/BookRst.aspx?K1=&K2=&K3=&K4=&N1=&Y1=&M1=&D1=&Y2=&M2=&D2=']

    def parse_start_url(self, response):
        self.logger.info('A response from start_url %s just arrived!', response.url)
        mnddecisiontablelist = {
            'decisionDate':response.xpath('//table[contains(@class,"tabeng")]//tr[position()>=1]/td[2]/text()').getall(),
            'caseid':response.xpath('//table[contains(@class,"tabeng")]//tr[position()>=1]/td[3]/a/text()').getall(),
            'link':response.xpath('//table[contains(@class,"tabeng")]//tr[position()>=1]/td[3]/a/@href').getall(),
        }
        self.mnddecisionlist = {}
        for itemi,link in enumerate(mnddecisiontablelist['link']):
            self.mnddecisionlist[link] = {
                'DCS_FILEID':mnddecisiontablelist['caseid'][itemi].strip(),
                'decisionDate':mnddecisiontablelist['decisionDate'][itemi].strip(),
                'link':link,
                }
            yield response.follow(link, callback=self.parse_single_decision_page, meta={'meta':self.mnddecisionlist[link]})

        bottommenu = response.xpath('//a[@id="hlNext"]/text()').getall()
        has_next = '下一頁' in bottommenu
        if has_next:
            bottommenuLinks = response.xpath('//a[@id="hlNext"]/@href').getall()
            bottommenuLinks = {bottommenu[linki]:link for linki,link in enumerate(bottommenuLinks)}
            yield response.follow(bottommenuLinks['下一頁'], callback=self.parse_start_url)

    def parse_single_decision_page(self, response):
        self.logger.info('A response from single_decision_page %s just arrived!', response.url)
        item = response.meta.get('meta')
        #因為原始頁面有不明錯誤，所以用自訂的html解析器lxml而不用scrapy內建的
        responsetext = response.text
        responsetext = responsetext.replace('\u3000','').replace('<br>',"\n").replace('<br />',"\n").replace('　','').strip()
        decisionContent = lxml.html.fromstring(responsetext)
        decisionContent = decisionContent.xpath('//span[@class="text-pre"]//text()')[0]
        decisionContent = decisionContent.replace(' ','')
        decisionContent = re.sub('(號)[\s　\n]*(再?[\s　\n]*審?[\s　\n]*申[\s　\n]*請[\s　\n]*人：)',r'\1\n再審申請人：',decisionContent)
        decisionContent = re.sub('(號)[\s　\n]*(訴[\s　\n]*願[\s　\n]*人：)',r'\1\n訴願人：',decisionContent)
        decisionContent = req.parse_with_regexp_on_whole_str(decisionContent)
        decisionContent = {**decisionContent, **item}
        yield decisionContent