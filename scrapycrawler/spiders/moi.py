import scrapy,json,re,time
import scrapycrawler.spiders.req as req
import pathlib,inspect

srcfile = inspect.getfile(lambda: None)
srcfileUrl = pathlib.Path(srcfile).parent.parent.parent / 'moi_petitions_list.html'
srcfileUrl = srcfileUrl.as_uri()

class MoiSpider(scrapy.spiders.CrawlSpider):

    name = 'moi'
    start_urls = [srcfileUrl]
    custom_settings = {'ROBOTSTXT_OBEY':False}

    def __init__(self, *args, **kwargs):
        super(MoiSpider).__init__(*args, **kwargs)
        petitions_list_file = pathlib.Path(srcfile).parent.parent.parent / 'moi_petitions_list.html'
        print(f'petitions_list_file is {petitions_list_file}')

    def parse_start_url(self, response):
        self.logger.info('A response from start_url %s just arrived!', response.url)
        self.moideisionlist = {
            'link':response.xpath('//*[@id="main_content"]/div/div/div[1]/table//tr[position()>=1]/td[2]/a/@href').getall(),
            'caseid':response.xpath('//*[@id="main_content"]/div/div/div[1]/table//tr[position()>=1]/td[2]/a/text()').getall(),
            'decisionDate':response.xpath('//*[@id="main_content"]/div/div/div[1]/table//tr[position()>=1]/td[3]/text()').getall(),
            'decisionID':response.xpath('//*[@id="main_content"]/div/div/div[1]/table//tr[position()>=1]/td[4]/text()').getall(),
            'mainDecision':response.xpath('//*[@id="main_content"]/div/div/div[1]/table//tr[position()>=1]/td[5]/text()').getall(),
        }
        self.moideisionlist['mainDecision'] = [t.strip() for t in self.moideisionlist['mainDecision']]
        for linki,link in enumerate(self.moideisionlist['link']):
            self.moideisionlist[link] = {
                'link':link,
                'caseid':self.moideisionlist['caseid'][linki],
                'decisionDate':self.moideisionlist['decisionDate'][linki],
                #'decisionID':self.moideisionlist['decisionID'][linki],
                'mainDecision':self.moideisionlist['mainDecision'][linki],
            }
            yield response.follow(link, callback=self.parse_single_decision_page, meta={'meta':self.moideisionlist[link]})

    def parse_single_decision_page(self, response):
        self.logger.info('A response from single_decision_page %s just arrived!', response.url)
        item = response.meta.get('meta')
        decisionContent = response.xpath('//*[@id="main_content"]/div/div/div[1]/div').extract()[0]
        decisionContent = req.parse_clean_and_split_decision_by_tag(decisionContent)
        decisionContent = req.parse_decision(decisionContent)
        decisionContent = {**decisionContent, **item}
        if isinstance(decisionContent,str): decisionContent = {'decisionContent':decisionContent}
        yield decisionContent
        #time.sleep(1)