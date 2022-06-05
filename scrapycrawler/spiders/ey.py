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

class EySpider(scrapy.spiders.CrawlSpider):
    name = 'ey'
    custom_settings = {
        'ROBOTSTXT_OBEY':False,
        'CONCURRENT_ITEMS':5,
        'CONCURRENT_REQUESTS':5,
        'CONCURRENT_REQUESTS_PER_DOMAIN':5,
        'DEPTH_LIMIT':999999999999999999999999,
        }

    def __init__(self):
        super().__init__()
        self.init_fetch = req.fetch("https://appeal.ey.gov.tw/Search/Search01/Read", {
            "headers": {
                "accept": "*/*",
                "accept-language": "zh-TW,zh;q=0.9",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "sec-ch-ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"101\", \"Google Chrome\";v=\"101\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "x-requested-with": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36 Edg/101.0.1210.39"
                #"Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36"
            },
            "referrerPolicy": "no-referrer",
            "body": "PageNo=1&Name=&Reason=&No=&CaseNo=&StartDateString=101%2F01%2F01&EndDateString=111%2F05%2F31&Keyword=&ConditionType=and&MultiKeyword[0].ConditionType=and",
            #"body": "PageNo=1&Name=&Reason=&No=&CaseNo=&StartDateString=101%2F01%2F01&EndDateString=111%2F05%2F31&Keyword=&ConditionType=and&MultiKeyword[0].ConditionType=and",
            "method": "POST",
            "mode": "cors",
            "credentials": "include"
            })

    def start_requests(self):
        tempres = scrapy.FormRequest(
            self.init_fetch['queryUrl'],
            formdata=self.init_fetch['payloads_flattened'],
            headers=self.init_fetch['headers'],
            callback=self.parse
            )
        """
        scrapy.http.Request(
            url=self.init_fetch['queryUrl'],
            callback=self.parse,
            method='POST',
            headers=self.init_fetch['headers'],
            body=json.dumps(self.init_fetch['payloads_flattened'])
        )
        """
        return [tempres]

    def parse(self, response, debug=True):
        # here you would extract links to follow and return Requests for
        # each of them, with another callback
        resp = json.loads(response.body)
        nextPageNum = int(resp['PageNo'])+1
        has_next = nextPageNum in resp['PageCount']
        if debug:
            checkMessage = "lastpageCount is {} and nextpage is {} and has_next is {}".format(resp['PageCount'][-1], nextPageNum, has_next)
            self.logger.info(checkMessage)

        for eypetitiondata_i,eypetitiondata in enumerate(resp['Data']):
            if debug:
                self.logger.info('loop over eypetitiondata {} of {} at page {}'.format(eypetitiondata_i+1, len(resp['Data']), resp['PageNo'] ) )
            if len(eypetitiondata['DCS_FULLTEXT'])>=1:
                textinf = req.parse_clean_and_split_decision_by_tag(eypetitiondata['DCS_FULLTEXT'])
                if debug:
                    self.logger.info('complete raw parse_clean_and_split_decision_by_tag')
                textinf = req.parse_with_regexp_on_whole_str("\n".join(textinf))
                if debug:
                    self.logger.info('complete raw parse_decision')
            if len(eypetitiondata['DCS_FULLTEXT'])<=1: #PDF的情形
                textinf = req.parse_text_file(eypetitiondata, urlformat='https://appeal.ey.gov.tw/File/Decision/{}')
                if debug:
                    self.logger.info('complete pdf parse_text_file')
                textinf = req.parse_with_regexp_on_whole_str("\n".join(textinf)) if len(textinf)>0 else {}
                if debug:
                    self.logger.info('complete pdf parse_decision')
            eypetitiondata = {**eypetitiondata, **textinf}
            if debug:
                self.logger.info('complete merge dict')
            try:
                eypetitiondata['decisionDate'] = eypetitiondata['DCS_DATE']
                eypetitiondata['motivation'] = eypetitiondata['DCS_MASKEDSHORTREASON']
                eypetitiondata['fulltext'] = eypetitiondata['DCS_FULLTEXT']
                eypetitiondata.pop('DCS_DATE', None)
                eypetitiondata.pop('DCS_FULLTEXT', None)
                eypetitiondata.pop('DCS_MASKEDSHORTREASON', None)
            except Exception as e:
                if debug:
                    self.logger.info('error for {}'.format(e))
                raise(e)

            yield(eypetitiondata)

        if has_next:
            anotherformdata = {**self.init_fetch['payloads_flattened'], **{'PageNo':str(nextPageNum)}}
            yield scrapy.FormRequest(
                self.init_fetch['queryUrl'],
                formdata=anotherformdata,
                headers=self.init_fetch['headers'],
                callback=self.parse
            )
        else:
            from scrapy.shell import inspect_response
            inspect_response(response, self)

    def backup_parse_line_by_line(self, response, debug=True):
        # here you would extract links to follow and return Requests for
        # each of them, with another callback
        resp = json.loads(response.body)
        nextPageNum = int(resp['PageNo'])+1
        has_next = nextPageNum in resp['PageCount']
        if debug:
            checkMessage = "lastpageCount is {} and nextpage is {} and has_next is {}".format(resp['PageCount'][-1], nextPageNum, has_next)
            self.logger.info(checkMessage)

        for eypetitiondata_i,eypetitiondata in enumerate(resp['Data']):
            if debug:
                self.logger.info('loop over eypetitiondata {} of {} at page {}'.format(eypetitiondata_i+1, len(resp['Data']), resp['PageNo'] ) )
            if len(eypetitiondata['DCS_FULLTEXT'])>=1:
                textinf = req.parse_clean_and_split_decision_by_tag(eypetitiondata['DCS_FULLTEXT'])
                if debug:
                    self.logger.info('complete raw parse_clean_and_split_decision_by_tag')
                textinf = req.parse_decision(textinf)
                if debug:
                    self.logger.info('complete raw parse_decision')
            if len(eypetitiondata['DCS_FULLTEXT'])<=1: #PDF的情形
                textinf = req.parse_text_file(eypetitiondata)
                if debug:
                    self.logger.info('complete pdf parse_text_file')
                textinf = req.parse_decision(textinf) if len(textinf)>0 else {}
                if debug:
                    self.logger.info('complete pdf parse_decision')
            eypetitiondata = {**eypetitiondata, **textinf}
            if debug:
                self.logger.info('complete merge dict')
            try:
                eypetitiondata['decisionDate'] = eypetitiondata['DCS_DATE']
                eypetitiondata['motivation'] = eypetitiondata['DCS_MASKEDSHORTREASON']
                eypetitiondata['fulltext'] = eypetitiondata['DCS_FULLTEXT']
                eypetitiondata.pop('DCS_DATE', None)
                eypetitiondata.pop('DCS_FULLTEXT', None)
                eypetitiondata.pop('DCS_MASKEDSHORTREASON', None)
            except Exception as e:
                if debug:
                    self.logger.info('error for {}'.format(e))
                raise(e)

            yield(eypetitiondata)

        if has_next:
            anotherformdata = {**self.init_fetch['payloads_flattened'], **{'PageNo':str(nextPageNum)}}
            yield scrapy.FormRequest(
                self.init_fetch['queryUrl'],
                formdata=anotherformdata,
                headers=self.init_fetch['headers'],
                callback=self.parse
            )
            """scrapy.http.Request(
                url=self.init_fetch['queryUrl'],
                callback=self.parse,
                method='POST',
                headers=self.init_fetch['headers'],
                body=json.dumps(anotherformdata)
            )
            """
        else:
            from scrapy.shell import inspect_response
            inspect_response(response, self)

    def parse_backup(self, response):
        # here you would extract links to follow and return Requests for
        # each of them, with another callback
        # error at now handling R:\\9fffc310-ee32-442e-91a9-8df5626bc294.pdf
        resp = json.loads(response.body)
        for eypetitiondata in resp['Data']:
            if len(eypetitiondata['DCS_FULLTEXT'])>=1:
                textinf = req.parse_clean_and_split_decision_by_tag(eypetitiondata['DCS_FULLTEXT'])
                textinf = req.parse_decision(textinf)
            if len(eypetitiondata['DCS_FULLTEXT'])<=1: #PDF的情形
                textinf = req.parse_text_file(eypetitiondata)
                textinf = req.parse_decision(textinf) if len(textinf)>0 else {}
            eypetitiondata = {**eypetitiondata, **textinf}
            eypetitiondata['decisionDate'] = eypetitiondata['DCS_DATE']
            eypetitiondata['motivation'] = eypetitiondata['DCS_MASKEDSHORTREASON']
            eypetitiondata['fulltext'] = eypetitiondata['DCS_FULLTEXT']
            eypetitiondata.pop('DCS_FULLTEXT', None)
            eypetitiondata.pop('DCS_DATE', None)
            eypetitiondata.pop('DCS_MASKEDSHORTREASON', None)
            yield(eypetitiondata)
            #break
        nextPageNum = int(resp['PageNo'])+1
        has_next = nextPageNum in resp['PageCount']
        if has_next:
            anotherformdata = {**self.init_fetch['payloads_flattened'], **{'PageNo':str(nextPageNum)}}
            yield scrapy.FormRequest(
                self.init_fetch['queryUrl'],
                formdata=anotherformdata,
                headers=self.init_fetch['headers'],
                callback=self.parse
            )
            """scrapy.http.Request(
                url=self.init_fetch['queryUrl'],
                callback=self.parse,
                method='POST',
                headers=self.init_fetch['headers'],
                body=json.dumps(anotherformdata)
            )
            """