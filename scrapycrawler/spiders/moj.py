import scrapy,json,six,re,time,io,pathlib,lxml
import scrapycrawler.spiders.req as req
import pandas as pd
import logging,time
from pdfminer.high_level import extract_pages as pdfminerExtractPages
from pdfminer.layout import LTTextContainer as pdfminerLTTextContainer
from os.path import exists
import threading, queue

logging.getLogger("pdfminer").setLevel(logging.WARNING)

class MOJSpider(scrapy.spiders.CrawlSpider):
    name = 'moj'
    custom_settings = {
        'ROBOTSTXT_OBEY':False,
        'CONCURRENT_ITEMS':2,
        'CONCURRENT_REQUESTS':2,
        'CONCURRENT_REQUESTS_PER_DOMAIN':2,
        'DEPTH_LIMIT':999999999999999999999999,
        'CLOSESPIDER_ERRORCOUNT':1,
        }
    start_urls = ['https://www.moj.gov.tw/2204/2645/2686/?Page=1&PageSize=60&type=']

    def parse_start_url(self, response):
        self.logger.info('A response from start_url %s just arrived!', response.url)
        mojdecisiontablelist = {
            'link':response.xpath('//*[@id="center"]/div/div[2]/section/div[2]/ul/li[position()>=1]/a/@href').getall(),
        }
        self.mojdecisiontablelist = {}

        for itemi,link in enumerate(mojdecisiontablelist['link']):
            link = req.make_complete_url(link,response.url)
            casebrief = response.xpath('//*[@id="center"]/div/div[2]/section/div[2]/ul/li[position()={}]/a//text()'.format(itemi+1)).getall()
            casebrief = "".join(casebrief)
            casebrief = re.sub('\d+[\r\n\s]+','',casebrief).strip()
            casebrief = casebrief.replace('/','-').replace('\\','-')
            decisiondate = re.findall(r'[\(（]{1}([\d\/-]+)',casebrief)
            try:
                if len(decisiondate)==0:
                    decisiondate = None
                elif decisiondate=='':
                    decisiondate = None
                else:
                    decisiondate = decisiondate[0]
            except Exception as e:
                self.logger.info(f'error in trying decisiondate at {casebrief} for {e}; source decisiondate is {decisiondate}')
                raise(e)

            dataformat = req.check_file_type(link)
            tempfilepath = pathlib.Path(req.tempLocalFolderpath, '{}.{}'.format(casebrief, dataformat))
            
            self.mojdecisiontablelist[link] = {
                'DCS_FILEID':casebrief.strip(),
                'fileurl':link,
                'decisiondate':decisiondate,
                'dataformat':dataformat
                }
            #self.logger.info(self.mojdecisiontablelist[link])
            if re.search('normalFile',link)!=None:
                self.mojdecisiontablelist[link]['dataformat'] = None
                yield self.mojdecisiontablelist[link]
            elif tempfilepath.is_file():
                yield self.parse_single_decision_page_no_response(self.mojdecisiontablelist[link])
            else:
                yield response.follow(link, callback=self.parse_single_decision_page, meta={'meta':self.mojdecisiontablelist[link]})

        bottommenu = response.xpath('//li[@class="next"]/a/@title').getall()
        has_next = '下一頁' in bottommenu
        self.logger.info(f'下一頁 is {has_next}, bottommenu is {bottommenu}, response.url is {response.url}')
        if has_next:
            #法訴字第10313503880號 蔡峯宗因聲請提起非常上訴案件(1031107）
            #法訴字第10213500330號 范?琪因申請閱覽案件(20130227)
            bottommenuLinks = response.xpath('//li[@class="next"]/a/@href').getall()
            bottommenuLinks = {bottommenu[linki]:req.make_complete_url(link,response.url) for linki,link in enumerate(bottommenuLinks)}
            bottommenuLink = [*bottommenuLinks.values()][0]
            self.logger.info(f'bottommenuLinks is {bottommenuLinks}')
            try:
                yield response.follow(bottommenuLink, callback=self.parse_start_url)
            except Exception as followError:
                self.logger.info(f'error at {bottommenuLink} for {followError}')
                raise(followError)

    def parse_single_decision_page_no_response(self, item):
        match item['dataformat']:
            case 'pdf'|'docx'|'doc'|'odt':
                decisionContent = req.parse_text_file(item, dataformat=item['dataformat'])
                decisionContent = "\n".join(decisionContent)
                if re.search('[\u4E00-\u9FFF\uF900-\uFAFF]+',decisionContent)==None:
                    self.logger.info(item)
                    time.sleep(10)
                decisionContent = req.parse_with_regexp_on_whole_str(decisionContent)
                decisionContent = {**decisionContent, **item}
                return decisionContent
            case 'html':
                filelink = req.fetch(item['fileurl'], {'method':'GET'},True)['responsetext']
                filelink = lxml.html.fromstring(filelink)
                filelink = filelink.xpath('//*[@id="center"]/div/div[2]/div[4]/ul/li/a/@href')[0]
                dataformat = req.check_file_type(filelink)
                filelink = req.make_complete_url(filelink,item['fileurl'])
                item['fileurl'] = filelink
                item['dataformat'] = dataformat
                return self.parse_single_decision_page_no_response(item)
        #self.logger.info(f'complete {response.url}, DCS_FILEID is {item["DCS_FILEID"]}, dataformat is {dataformat}') #, decisionContent is {decisionContent}
        #time.sleep(5)

    def parse_single_decision_page(self, response):
        self.logger.info('A response from single_decision_page %s just arrived!', response.url)
        item = response.meta.get('meta')
        #item['responsebody'] = response.body
        yield self.parse_single_decision_page_no_response(item)

"""
整理資料後發現以下錯誤與應更正情形：
* 法訴字第10813501970號鄭兆庭因聲請應用檔案事件(1080320) 連結內容頁面是空的
* 法訴字第10813501810號謝清彥不服本部107年9月14日法訴字第10713505930號及第10713505940號訴願決定(1080320) 連結內容頁面是空的
法訴字第10813501130號謝清彥因申請應用檔案事件(1080226) 連結內容頁面是空的
* 法訴字第10413500570號  謝清彥因申請提供政府資訊事件(1040123） 連結內容頁面是空的
* 法訴字第10313500810號 耿漢生因陳情事(1030219) 連結內容頁面是空的
* 法訴字第10213501260號 戴興良因申請再任事件(20130328) 訴願人處 「戴興良  出」 多了一個 生 字
* https://www.moj.gov.tw/media/6205/629180806102638322.pdf?mediaDL=true 法訴字第 10713504440 號 決定 身分資料放在上面

"""