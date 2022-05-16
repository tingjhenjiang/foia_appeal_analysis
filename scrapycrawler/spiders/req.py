import requests,json,six,re,json,sys,time,scrapy,os
from lxml import etree
from lxml.html.clean import Cleaner
from multiprocessing import cpu_count
from IPython.display import display
from pdfminer.high_level import extract_pages as pdfminerExtractPages
from pdfminer.layout import LTTextContainer as pdfminerLTTextContainer

workers = cpu_count()
default_req_headers = requests.utils.default_headers()
tempLocalFolderpath = 'R:\\\\'

def fetch(fetchsrc, headers, reqresponse=False):
    """
    a typical fetch from browser is like this
    fetch("https://appeal.ey.gov.tw/Search/Search01/Read", {
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
        "x-requested-with": "XMLHttpRequest"
    },
    "referrerPolicy": "no-referrer",
    "body": "PageNo=1&Name=&Reason=&No=&CaseNo=&StartDateString=101%2F01%2F01&EndDateString=108%2F05%2F31&Keyword=&ConditionType=and&MultiKeyword[0].ConditionType=and",
    "method": "POST",
    "mode": "cors",
    "credentials": "include"
    });
    """
    reqcontent = {k:v for k,v in headers.items() if k!='headers'}
    payloads = six.moves.urllib.parse.parse_qs(reqcontent['body'])
    payloads_flattened = {k:v[0] for k,v in payloads.items()}
    session = requests.Session()
    if reqresponse==True:
      if reqcontent['method']=='POST':
        response = session.post(fetchsrc, data = payloads_flattened) #, cookies=setcookies
      else:
        response = session.get(fetchsrc)
    returnd = {
      'queryUrl': fetchsrc,
      'headers': headers['headers'],
      'reqdetails': reqcontent,
      'payloads': payloads,
      'payloads_flattened': payloads_flattened,
      }
    if reqresponse==True:
      returnd['response'] = response
      returnd['responsetext'] = response.text
    return returnd

def savejsontofile(content, targetfilename):
    with open(targetfilename, "w", encoding="utf-8") as outfile:
        res = json.dump(content, outfile, ensure_ascii=False)
    return res

def loadfromjson(srcfilename):
    with open(srcfilename, "r") as srcfile:
        res = json.load(srcfile)
    return res

def sortdictbykey(d):
    return {k:d[k] for k in sorted(d)}

def chunks(li, n):
    if li == []:
        return
    yield li[:n]
    yield from chunks(li[n:], n)

def daskcompute_by_segments(lst, size=3, scheduler='threads', num_workers=workers):
    newlst = list()
    parts = chunks(lst, size)
    for part in parts:
        newlst.extend(dask.compute(*part, scheduler=scheduler, num_workers=num_workers))
    time.sleep(0.5)
    return newlst

def try_except(success, failure, *exceptions):
    try:
        return success
    except exceptions or Exception:
        return failure() if callable(failure) else failure

def openfileandread(tfile, mode='r', encoding='utf-8'):
    with open(tfile, mode, encoding=encoding) as f:
        filecontents = {
            'full':f.read(),
            'lines':f.readlines()
        }
        f.close()
    return filecontents

def downloadfile(src, dst, urllib=False):
    result = ''
    try:
        if urllib==True:
            result = six.moves.urllib.request.urlretrieve(src, dst)
        else:
            r = requests.get(src, allow_redirects=True)
            with open(dst, 'wb') as f:
                result = f.write(r.content)
                f.close()
    except Exception as result:
        print(str(result))
    return result

def furtherSplit(lst, delimeter='<br/>'):
    newelements = []
    for item in lst:
        newelements.extend(item.split(delimeter))
    return newelements

def removeElement(lst, removeItem=''):
    i = 0
    while i<len(lst):
        if (lst[i] is removeItem):
            lst.pop(i)
        else:
            i += 1
    return lst

def juddata_std_reqHeader():
    header = {
        'Host': 'law.judicial.gov.tw',
        'Origin': "https://law.judicial.gov.tw",
        'Referer': "https://law.judicial.gov.tw/FJUD/Default_AD.aspx",
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    }
    return header

def parse_clean_and_split_decision_by_tag(texts):
    texts = re.sub('[\r\n\t]+','',texts)
    texts = re.findall(r'<[^>]*>.*?</[^>]*>(?:<[^>]*/>)?|[^<>]+', texts)
    texts = removeElement(texts,'')
    texts = removeElement(texts,None)
    texts = furtherSplit(texts,'<br/>')
    texts = furtherSplit(texts,'<br>')
    texts = furtherSplit(texts,'<br />')
    texts = [t.strip().replace('\u3000','').replace('&nbsp; ','').replace('&nbsp;','').replace(' ','') for t in texts]
    texts = [re.sub(re.compile('<.*?>'), '', t) for t in texts]
    texts = removeElement(texts,'')
    texts = removeElement(texts,None)
    return texts

def parse_pdf(eypetitiondata):
    #108年12月31日以前收辦訴願案件訴願決定書內容以網頁方式呈現。
    #https://appeal.ey.gov.tw/File/Decision/fb921939-8b27-4e35-8ebb-c6ecd155e613
    #{'DCS_ID': 'A-111-000404', 'DCS_DATE': '111/04/21', 'DCS_MASKEDSHORTREASON': '瀚威國際顧問有限公司因入出國及移民法事件', 'DCS_FULLTEXT': '', 'DCS_FILEID': 'c3477865-40ce-47d7-a1cb-e34f12581372'}
    #pass
    pdfurl = 'https://appeal.ey.gov.tw/File/Decision/{}'.format(eypetitiondata['DCS_FILEID'])
    tempErrorRecordsFilePath = '{}scrapyErrors.txt'.format(tempLocalFolderpath)
    tempfilepath = '{}{}.pdf'.format(tempLocalFolderpath, eypetitiondata['DCS_FILEID'])
    if not os.path.exists(tempfilepath): downloadfile(pdfurl, tempfilepath)
    #reader = tabula.io.read_pdf(tempfilepath, pages='all', pandas_options={'header':None})
    elements = []
    print(f'now handling {tempfilepath}')
    tryn = 0
    try:
        for page_layout in pdfminerExtractPages(tempfilepath):
            for element in page_layout:
                if isinstance(element, pdfminerLTTextContainer):
                    element = element.get_text().strip().replace(' ','')
                    if element!='':
                        elements.extend(element.split("\n"))
    except Exception as e:
        errorHint = f"\n error at {eypetitiondata} for {e}"
        with open(tempErrorRecordsFilePath, 'a+') as f:
            f.write(errorHint)
            f.close()
        elements = []
    return elements

def parse_decision(eypetitiondata_lines):
    #{'DCS_ID': '41172', 'DCS_DATE': '108/12/07', 'DCS_MASKEDSHORTREASON': '台灣世曦工程顧問股份有限公司因違反職業安全衛生法事件', 'DCS_FULLTEXT': '院臺訴字第1080196579號<br/><p>行 政 院 訴 願 決 定 書\u3000&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 院臺訴字第1080196579號</p>\r\n\r\n<p>\u3000訴願人：台灣世曦工程顧問股份有限公司</p>\r\n\r\n<p>\u3000代表人：周禮良</p>\r\n\r\n<p>\u3000訴願人因違反職業安全衛生法事件，不服勞動部107 年12月17日勞職授字第1070204953號處分，提起訴願，本院決定如下：</p>\r\n\r\n<p>\u3000\u3000主\u3000\u3000文</p>\r\n\r\n<p>訴願不受理。</p>\r\n\r\n<p>\u3000\u3000理\u3000\u3000由</p>\r\n\r\n<table class="layout">\r\n\t<tbody>\r\n\t\t<tr>\r\n\t\t\t<td valign="top" width="2%">一、</td>\r\n\t\t\t<td>按訴願法第77條第6款規定，訴願事件行政處分已不存在者，應為不受理之決定。</td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td valign="top">二、</td>\r\n\t\t\t<td>原處分機關勞動部以訴願人辦理「第C009標臺灣桃園國際機場WC滑行道遷建及雙線化工程」(以下簡稱遷建工程)之委託設計及監造技術服務案，使現場監造工程師桂君於107年8月21日早上約10時在桃園市大園區桃園機場對訴願人所監造之遷建工程位於航站北路與環場西路交叉口之污水、自來水及消防管線遷移配管地點，從事測量驗收拍照，該地點為開挖深度1.5公尺以上未設擋土支撐之露天開挖工作場所，違反營造安全衛生設施標 準第71條第1項暨職業安全衛生法第6條第1項第5款規定，經該部職業安全衛生署於107年8月21日派員實施勞動檢查時發現，依同法第43條第2款及第49條第2款規定，以107年12月17日勞職授字第1070204953號處分書處訴願人罰鍰新臺幣12萬元，並公布訴願人名稱及負責人姓名。訴願人不服，提起訴願。</td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td valign="top">三、</td>\r\n\t\t\t<td>查原處分機關經重新審查，因裁罰額度尚有審酌餘地，以108年12月2日勞職授 字第10802052241號函撤銷上開處分，有該撤銷函副本在卷可稽，是本件行政處分已不存在，訴願人所提訴願應不受理。</td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td valign="top">四、</td>\r\n\t\t\t<td>據上論結，本件訴願為不合法，依訴願法第77條第6款決定如主文。</td>\r\n\t\t</tr>\r\n\t</tbody>\r\n\t<tbody>\r\n\t</tbody>\r\n</table>\r\n\r\n<p style="text-align: right;">訴願審議委員會主任委員 林 秀 蓮<br />\r\n委員 陳 愛 娥<br />\r\n委員 陳 素 芬<br />\r\n委員 蔡 茂 寅<br />\r\n委員 郭 麗 珍<br />\r\n委員 李 寧 修<br />\r\n委員 林 春 榮<br />\r\n委員 沈 淑 妃<br />\r\n委員 黃 育 勳<br />\r\n委員 林 明 鏘</p>\r\n\r\n<p>中\u3000華\u3000民\u3000國\u3000108\u3000年\u300012\u3000月\u30004\u3000日</p>\r\n\r\n<p>如不服本決定，得於決定書送達之次日起2個月內向臺北高等行政法院提起行政訴訟。</p>\r\n', 'DCS_FILEID': None}
    elements = []
    key_cols = {'decisionmembers':[],'decisionmembers_pos':[]}
    elementi = 0
    checkItemsQue = ['petitioner_pos','decision_made_by','motivation_pos','maindecision_pos','fact_pos','reason_pos','chief_pos','decisionmembers_pos']
    while elementi<len(eypetitiondata_lines):
        element = eypetitiondata_lines[elementi]
        if len(checkItemsQue)>0:
            match checkItemsQue[0]:
                case 'petitioner_pos':
                    if re.search('(訴願人：|再審申請人：|代表人：)',element)!=None:
                        key_cols['petitioner_pos'] = elementi
                        checkItemsQue = [v for v in checkItemsQue if v!='petitioner_pos']
                case 'decision_made_by':
                    if element in ['原處分機關','原處分機關：'] or re.search('^原處分機關：.+$', element)!=None:
                        key_cols['decision_made_by_pos'] = elementi
                        key_cols['decision_made_by'] = element
                        key_cols['petitioners'] = elements[key_cols['petitioner_pos']:key_cols['decision_made_by_pos']]
                        key_cols['petitioners'] = [v.replace('訴願人：','').replace('再審申請人：','') for v in key_cols['petitioners']]
                        key_cols['petitioners'] = "".join(key_cols['petitioners'])
                        checkItemsQue = [v for v in checkItemsQue if v!='decision_made_by']
                    if elementi==len(eypetitiondata_lines)-1: #找不到原處分機關欄時，就直接不再找
                        checkItemsQue = [v for v in checkItemsQue if v!='decision_made_by']
                        elementi = key_cols['petitioner_pos']
                case 'motivation_pos':
                    if re.search('(^訴願人等?因.+(事件，)?|^訴願人等?提起訴願，|^再審申請人申請再審|^訴願人不服.+部|^再審申請人等?因.+事件，)',element)!=None:
                        key_cols['motivation_pos'] = elementi
                        if 'petitioners' not in key_cols:
                            key_cols['petitioners'] = elements[key_cols['petitioner_pos']:key_cols['motivation_pos']]
                            key_cols['petitioners'] = [v.replace('訴願人：','').replace('再審申請人：','') for v in key_cols['petitioners']]
                            key_cols['petitioners'] = "".join(key_cols['petitioners'])
                        checkItemsQue = [v for v in checkItemsQue if v!='motivation_pos']
                case 'maindecision_pos':
                    if element in ['主文','主文：']:
                        key_cols['maindecision_pos'] = elementi
                        key_cols['motivation'] = "".join(elements[key_cols['motivation_pos']:]).replace('，提起訴願，本院決定如下：','').replace('本院決定如下：','')
                        checkItemsQue = [v for v in checkItemsQue if v!='maindecision_pos']
                case 'fact_pos':
                    if element in ['事實','事實：']:
                        key_cols['fact_pos'] = elementi
                        key_cols['maindecision'] = "".join(elements[key_cols['maindecision_pos']+1:])
                        checkItemsQue = [v for v in checkItemsQue if v!='fact_pos']
                    if elementi==len(eypetitiondata_lines)-1: #找不到事實欄時，就直接不再找
                        checkItemsQue = [v for v in checkItemsQue if v!='fact_pos']
                        elementi = key_cols['maindecision_pos']
                case 'reason_pos':
                    if element in ['理由','理由：']:
                        key_cols['reason_pos'] = elementi
                        if 'fact_pos' in key_cols:
                            key_cols['fact'] = "".join(elements[key_cols['fact_pos']+1:])
                        else:
                            key_cols['maindecision'] = "".join(elements[key_cols['maindecision_pos']+1:])
                        checkItemsQue = [v for v in checkItemsQue if v!='reason_pos']
                case 'chief_pos':
                    if re.search('(訴願審議委員會主任委員|訴願審議委員會副主任委員)',element)!=None:
                        key_cols['chief_pos'] = elementi
                        key_cols['reason'] = "".join(elements[key_cols['reason_pos']+1:])
                        key_cols['decisionmembers_pos'].append(elementi)
                        key_cols['decisionmembers'].append(element.replace('訴願審議委員會主任委員',''))
                        checkItemsQue = [v for v in checkItemsQue if v!='chief_pos']
                case 'decisionmembers_pos':
                    if re.search('^委員.{2,3}$',element)!=None:
                        key_cols['decisionmembers_pos'].append(elementi)
                        key_cols['decisionmembers'].append(element.replace('委員',''))
                    if elementi==len(eypetitiondata_lines)-1: #找到最後時，就直接不再找
                        checkItemsQue = [v for v in checkItemsQue if v!='decisionmembers_pos']


        """
        for element in eypetitiondata_lines:
            if 'petitioner_pos' not in key_cols:
                if re.search('(訴願人：|再審申請人：|代表人：)',element)!=None:
                    key_cols['petitioner_pos'] = i
            if 'motivation_pos' not in key_cols:
                if re.search('(^訴願人等?因.+(事件，)?|^訴願人等?提起訴願，|^再審申請人申請再審|^訴願人不服.+部|^再審申請人等?因.+事件，)',element)!=None:
                    key_cols['motivation_pos'] = i
                    if 'petitioner_pos' not in key_cols:
                        print(eypetitiondata_lines)
                    key_cols['petitioners'] = elements[key_cols['petitioner_pos']:key_cols['motivation_pos']]
                    key_cols['petitioners'] = [v.replace('訴願人：','').replace('再審申請人：','') for v in key_cols['petitioners']]
                    key_cols['petitioners'] = "".join(key_cols['petitioners'])
            if 'maindecision_pos' not in key_cols:
                if element=='主文':
                    key_cols['maindecision_pos'] = i
                    if 'motivation' not in key_cols:
                        print(eypetitiondata_lines)
                    key_cols['motivation'] = "".join(elements[key_cols['motivation_pos']:]).replace('，提起訴願，本院決定如下：','').replace('本院決定如下：','')
            if 'fact_pos' not in key_cols:
                if element=='事實':
                    key_cols['fact_pos'] = i
                    if 'maindecision' not in key_cols:
                        print(eypetitiondata_lines)
                    key_cols['maindecision'] = "".join(elements[key_cols['maindecision_pos']+1:])
            if 'reason_pos' not in key_cols:
                if element=='理由':
                    key_cols['reason_pos'] = i
                    if 'fact_pos' in key_cols:
                        key_cols['fact'] = "".join(elements[key_cols['fact_pos']+1:])
                    else:
                        if 'maindecision_pos' not in key_cols:
                            print(eypetitiondata_lines)
                        key_cols['maindecision'] = "".join(elements[key_cols['maindecision_pos']+1:])
            if 'chief_pos' not in key_cols:
                if re.search('(訴願審議委員會主任委員|訴願審議委員會副主任委員)',element)!=None:
                    key_cols['chief_pos'] = i
                    if 'reason_pos' not in key_cols:
                        print(eypetitiondata_lines)
                    key_cols['reason'] = "".join(elements[key_cols['reason_pos']+1:])
                    key_cols['decisionmembers_pos'].append(i)
                    key_cols['decisionmembers'].append(element.replace('訴願審議委員會主任委員',''))
            if 'decisionmembers_pos' not in key_cols:
                if re.search('^委員.{2,3}$',element)!=None:
                    key_cols['decisionmembers_pos'].append(i)
                    key_cols['decisionmembers'].append(element.replace('委員',''))
        """
        elements.append(element)
        elementi += 1
    key_cols['DCS_FULLTEXT'] = "\n".join(eypetitiondata_lines)
    key_cols['foia_related'] = 1 if re.search('政府資訊公開法', key_cols['DCS_FULLTEXT'])!=None else 0
    print(eypetitiondata_lines)
    return key_cols