import requests,json,six,re,json,sys,time,pathlib,os,io
from lxml import etree
from lxml.html.clean import Cleaner
from multiprocessing import cpu_count
from IPython.display import display
from pdfminer.high_level import extract_pages as pdfminerExtractPages
from pdfminer.layout import LTTextContainer as pdfminerLTTextContainer
import zipfile
import xml.dom.minidom
from functools import reduce

class OdfReader:
    def __init__(self,filename):
        """
        Open an ODF file.
        """
        self.filename = filename
        self.m_odf = zipfile.ZipFile(filename)
        self.filelist = self.m_odf.infolist()

    def showManifest(self):
        """
        Just tell me what files exist in the ODF file.
        """
        for s in self.filelist:
            #print s.orig_filename, s.date_time,
            s.filename, s.file_size, s.compress_size
            print(s.orig_filename)

    def flatten_nodes(self,parentnode):
        text_in_paras = []
        for ch in parentnode.childNodes:
            if ch.nodeType == ch.TEXT_NODE:
                text_in_paras.append(ch.data)
            else:
                text_in_paras.extend(self.flatten_nodes(ch))
        return text_in_paras

    def getContents(self):
        """
        Just read the paragraphs from an XML file.
        """
        ostr = self.m_odf.read('content.xml')
        doc = xml.dom.minidom.parseString(ostr)
        paras = doc.getElementsByTagName('text:p')
        #print("I have ", len(paras), " paragraphs ")
        self.text_in_paras = [self.flatten_nodes(p) for p in paras]
        self.text_in_paras = reduce(lambda x,y: x+y, self.text_in_paras)
        return self.text_in_paras

    def findIt(self,name):
        for s in self.text_in_paras:
            if name in s:
               print(s)

sys.setrecursionlimit(2140000000)
workers = cpu_count()
default_req_headers = requests.utils.default_headers()
tempLocalFolderpath = pathlib.Path('R:/').resolve()

not_found = 'not found'
checkItemsQueRecursive = {
    'petitioner_pos':'(訴願人：|再審申請人：|代表人：)',
    'decision_made_by_pos':'(^原處分機關$|^原處分機關：$|^原處分機關：.+$)',
    'motivation_pos':'(訴願人等?因.+(事件，)?|訴願人等?提起訴願，|再審申請人申請再審|訴願人不服.+部|再審申請人等?因.+事件，)',
    'maindecision_pos':'(^主文$|^主文：$|^主　　文$)',
    'fact_pos':'(^事實$|^事實：$)',
    'reason_pos':'(^理由$|^理由：$)',
    'chiefdecisionmember_pos':'(訴願審議委員會主任委員|訴願審議委員會副主任委員|訴願審議會主任)',
    'decisionmembers_pos':'委員.{2,3}$',
    }
pattern_chief_decision_member = '(訴願審議會主任|訴願審議委員會主任委員)(.*)'
replace_pattern_chief_decision_member = f'(決定如主文。).*{pattern_chief_decision_member}'


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
    try:
        payloads = six.moves.urllib.parse.parse_qs(reqcontent['body'])
        payloads_flattened = {k:v[0] for k,v in payloads.items()}
    except Exception as e:
        payloads = None
        payloads_flattened = None
    session = requests.Session()
    if reqresponse==True:
      if reqcontent['method']=='POST':
        response = session.post(fetchsrc, data = payloads_flattened) #, cookies=setcookies
      else:
        response = session.get(fetchsrc)
    if 'headers' not in headers:
        headers['headers'] = {}
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
      returnd['responsebody'] = response.content
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
    except Exception as e:
        print(f'error at {src} to {dst} for {e}')
        raise(e)
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

def all_equals_to_check(checkvalue, matchvalue):
    if isinstance(checkvalue, list):
        return all(c==matchvalue for c in checkvalue)
    else:
        return checkvalue==matchvalue

def merge_two_dicts(dicta, dictb):
    if len(dictb.keys())==0: return dicta
    for key,value in dictb.items():
        if key in dicta:
            try:
                value = [value] if not isinstance(value, list) else value
            except Exception as e:
                print('dictb is {}'.format(dictb))
                raise(e)
            try:
                dicta[key] = [dicta[key]] if not isinstance(dicta[key], list) else dicta[key]
            except Exception as e:
                print('dicta is {}'.format(dicta))
                raise(e)
            dicta[key].extend(value)
        else:
            dicta[key] = value
    return dicta            


def check_file_type(link):
    dataformat = re.findall('(pdf|docx|doc|odt)',link)
    try:
        if len(dataformat)==0 or dataformat in (None,''):
            dataformat = 'html'
        else:
            dataformat = dataformat[0]
    except Exception as e:
        print(f'error at {link} for dataformat is {dataformat}')
        raise(e)
    return dataformat

def make_complete_url(link, fullurlexample):
    #responseurlcomponents = six.moves.urllib.parse.urlparse(fullurlexample)
    if re.search('http', link)==None:
        link = six.moves.urllib.parse.urljoin(fullurlexample,link)
        return link
    else:
        return link

def parse_clean_and_split_decision_by_tag(texts):
    texts = re.sub('[\r\n\t]+','',texts)
    texts = re.findall(r'<[^>]*>.*?</[^>]*>(?:<[^>]*/>)?|[^<>]+', texts)
    texts = removeElement(texts,'')
    texts = removeElement(texts,None)
    texts = [re.sub(replace_pattern_chief_decision_member,r'\1<br />\2\3',t) for t in texts]
    texts = furtherSplit(texts,'<br/>')
    texts = furtherSplit(texts,'<br>')
    texts = furtherSplit(texts,'<br />')
    texts = [t.strip().replace('\u3000','').replace('&nbsp; ','').replace('&nbsp;','').replace(' ','') for t in texts]
    texts = [re.sub(re.compile('<.*?>'), '', t) for t in texts]
    texts = removeElement(texts,'')
    texts = removeElement(texts,None)
    return texts

def extract_texts_in_docx(targetfile, furtherprocess=True):
    """
    returns list
    """
    from docx import Document
    f = open(targetfile, 'rb')
    document = Document(targetfile)
    f.close()
    texts = [p.text.replace('\u3000','').replace('\t','').replace(' ','') for p in document.paragraphs]
    texts = [e for e in texts if e!='']
    if furtherprocess:
        texts = furtherprocess_after_extract(texts)
    return texts

def extract_texts_in_doc(targetfile, furtherprocess=True):
    """
    returns list
    """
    #print('now in extract_texts_in_doc')
    from subprocess import Popen, PIPE
    myenv = dict(os.environ)
    if 'LC_ALL' in myenv:
        del myenv['LC_ALL']
    myenv['LANG'] = 'zh-tw.UTF-8'
    cmd = ['antiword', targetfile]
    p = Popen(cmd, stdout=PIPE, env=myenv)
    stdout, stderr = p.communicate()
    texts = stdout.decode('utf-8', 'ignore')
    #print(f'texts is now {texts}')
    if re.search('I can.t open.+for reading', texts)!=None or texts=='':
        print(f'{texts} appears')
        import random
        temp_file_name = str(time.time()).replace('.','-')
        temp_file_name = '{}{}.doc'.format(temp_file_name, str(random.random()).replace('.','-') )
        newpath = targetfile.with_name(temp_file_name)
        print(f'newpath is {newpath}')
        targetfile.rename(targetfile.with_name(temp_file_name))
        return extract_texts_in_doc(targetfile.with_name(temp_file_name), furtherprocess=furtherprocess)
    else:
        texts = texts.split("\n")
        if furtherprocess:
            texts = furtherprocess_after_extract(texts)
        return texts

def extract_texts_in_odt(targetfile, furtherprocess=True):
    """
    returns list
    """
    myodf = OdfReader(targetfile)
    texts = myodf.getContents()
    if furtherprocess:
        texts = furtherprocess_after_extract(texts)
    return texts

def extract_texts_in_pdf(targetfile, furtherprocess=True):
    """
    returns list
    """
    texts = []
    try:
        for page_layout in pdfminerExtractPages(targetfile):
            for element in page_layout:
                if isinstance(element, pdfminerLTTextContainer):
                    element = element.get_text().strip().replace(' ','')
                    if element!='':
                        texts.extend(element.split("\n"))
    except Exception as e:
        errorHint = f"\n error at {targetfile} for {e}"
        print(errorHint)
        texts = []
        raise(e)
    if furtherprocess:
        texts = furtherprocess_after_extract(texts)
    return texts

def furtherprocess_after_extract(texts):
    """
    returns list
    """
    texts = [t.strip() for t in texts]
    texts = [t for t in texts if t!='']
    texts = "\n".join(texts).strip()
    texts = texts.replace('\n主\n文\n','\n主文\n')
    texts = texts.replace('\n文\n主\n','\n主文\n')
    texts = texts.replace('\n事\n實\n','\n事實\n')
    texts = texts.replace('\n實\n事\n','\n事實\n')
    texts = texts.replace('\n理\n由\n','\n理由\n')
    texts = texts.replace('\n由\n理\n','\n理由\n')
    texts = re.sub('\n主\s*文\n','\n主文\n',texts)
    texts = re.sub('\n事\s*實\n','\n事實\n',texts)
    texts = re.sub('\n理\s*由\n','\n理由\n',texts)
    texts = re.sub('決\n?定\n?如\n?下','決定如下',texts)
    #結合孤立文字 例如 申\n請\n人因申請\n提\n供\n政府資訊 裡面的 請 提 供
    isolated_characters = re.findall("((\n[\u4E00-\u9FFF\uF900-\uFAFF○]){2,})",texts)
    isolated_characters = [p[0] for p in isolated_characters]
    for isolated_character_i, isolated_character in enumerate(isolated_characters):
        concatenated_isolated_character = "".join(re.findall('[\u4E00-\u9FFF\uF900-\uFAFF○]',isolated_character))
        texts = texts.replace(isolated_character, concatenated_isolated_character)
    texts = re.sub('訴\n?願\n?審\n?議\n?委\n?員\n?會\n?主\n?任\n?委\n?員','訴願審議委員會主任委員',texts)
    texts = re.sub('\n?訴願人[\n\s]*([\u4E00-\u9FFF\uF900-\uFAFF○]+)\n((.|\n)*?)主文\n',r'\n訴願人：\1\n\2主文\n',texts)
    texts = re.sub('\n代理人[\n\s]*([\u4E00-\u9FFF\uF900-\uFAFF○]+)\n((.|\n)*?)主文\n',r'\n代理人：\1\n\2主文\n',texts)
    texts = re.sub('\n代表人[\n\s]*([\u4E00-\u9FFF\uF900-\uFAFF○]+)\n((.|\n)*?)主文\n',r'\n代表人：\1\n\2主文\n',texts)
    texts = re.sub('\n送達代收人[\n\s]*([\u4E00-\u9FFF\uF900-\uFAFF○]+)\n((.|\n)*?)主文\n',r'\n送達代收人：\1\n\2主文\n',texts)
    texts = re.sub('\n?再審申請人[\n\s]*([\u4E00-\u9FFF\uF900-\uFAFF○]+)\n((.|\n)*?)主文\n',r'\n再審申請人：\1\n\2主文\n',texts)
    texts = re.sub('(\d+)號\n申請人[\n\s]*([\u4E00-\u9FFF\uF900-\uFAFF○]+)\n((.|\n)*?)主文\n',r'\1號\n再審申請人：\2\n\3主文\n',texts)
    texts = re.sub('\n謝清彥主文\n','\n主文\n',texts)
    texts = texts.split('\n')
    return texts

def parse_text_file(eypetitiondata, dataformat='pdf', urlformat='https://appeal.ey.gov.tw/File/Decision/{}'):
    #print(f'eypetitiondata is {eypetitiondata}')
    #108年12月31日以前收辦訴願案件訴願決定書內容以網頁方式呈現。
    #https://appeal.ey.gov.tw/File/Decision/fb921939-8b27-4e35-8ebb-c6ecd155e613
    #{'DCS_ID': 'A-111-000404', 'DCS_DATE': '111/04/21', 'DCS_MASKEDSHORTREASON': '瀚威國際顧問有限公司因入出國及移民法事件', 'DCS_FULLTEXT': '', 'DCS_FILEID': 'c3477865-40ce-47d7-a1cb-e34f12581372'}
    #pass
    #tempErrorRecordsFilePath = '{}scrapyErrors.txt'.format(tempLocalFolderpath)
    tempErrorRecordsFilePath = pathlib.Path(tempLocalFolderpath, 'scrapyErrors.txt')#.resolve()
    #tempfilepath = '{}.{}'.format(tempLocalFolderpath, eypetitiondata['DCS_FILEID'], dataformat)
    tempfilepath = pathlib.Path(tempLocalFolderpath, '{}.{}'.format(eypetitiondata['DCS_FILEID'], dataformat))
    #print(f'tempfilepath is {tempfilepath}')
    if 'responsebody' in eypetitiondata:
        #if dataformat=='doc':
        with tempfilepath.open("wb") as f:
            f.write(eypetitiondata['responsebody'])
            f.close()
        #else:
        #    tempfilepath = io.BytesIO(eypetitiondata['responsebody']).read()
    elif 'fileurl' in eypetitiondata:
        fileurl = eypetitiondata['fileurl']
        if not tempfilepath.is_file(): downloadfile(fileurl, tempfilepath)
        #tempfilepath = fetch(fileurl, {}, reqresponse=True)['responsebody']
        #tempfilepath = io.BytesIO(eypetitiondata['responsebody'])
    elif 'fileurl' not in eypetitiondata:
        fileurl = urlformat.format(eypetitiondata['DCS_FILEID'])
        if not tempfilepath.is_file(): downloadfile(fileurl, tempfilepath)
    else:
        raise('necessary fileurl not provided')
    #reader = tabula.io.read_pdf(tempfilepath, pages='all', pandas_options={'header':None})
    elements = []
    #print(f'now handling {tempfilepath}')
    #tryn = 0
    #print('ready to extract')
    match dataformat:
        case 'pdf':
            elements = extract_texts_in_pdf(tempfilepath)
        case 'docx':
            elements = extract_texts_in_docx(tempfilepath)
        case 'doc':
            elements = extract_texts_in_doc(tempfilepath)
        case 'odt':
            elements = extract_texts_in_odt(tempfilepath)

    return elements

def parse_with_regexp_on_whole_str(decision_str):
    checkItemsQueRegExp = {
        'petitioner':'(?=(\n(訴願人：|再審申請人：|代表人：|訴願代理人：|訴願人代理人：|代理人：|送達代收人：){1}([^「\n]+)\n))',
        'decision_made_by':'\n(原處分機關：?){1}(.+)\n',
        'motivation':'\n(((上述|上列|上)?訴願人等?因?.+((事件|案件|行為)，)|(上述|上列|上)?訴願人等?提起訴願，|(上述|上列|上)?(再審)?申請人等?申請再審|(上述|上列|上)?訴願人等?不服.+部|(上述|上列|上)?(再審)?申請人等?因?.+(事件|案件|行為)，|(上述|上列|上)?申請人等?因?.+(事件|案件|行為)|(上述|上列|上)?(再審)?申請人等?因?不服|(上述|上列|上)?訴願人等?因?不服|(上述|上列|上)?訴願人等?稱不服|(上述|上列|上)?訴願人等?因?.*認|(上述|上列|上)?訴願人等?因依|(上述|上列|上)?訴願人等?因請求|(上述|上列|上)?訴願人等?因.+對.+|(上述|上列|上)?訴願人等?對.+決定.+|(上述|上列|上)?申請人等?對.+決定|(上述|上列|上)?訴願人等?因.+不服.+|(上述|上列|上)?訴願人等?[.\n]*因|(上述|上列|上)?訴願人等?與.+爭議|(上述|上列|上)?訴願人等?於.+年.+月.+日|(上述|上列|上)?訴願人等?就.+提起訴願|(上述|上列|上)?訴願人等?因.+處分|(上述|上列|上)?訴願人等?因本部|(上述|上列|上)?訴願人等?.*因.+駁回|(上述|上列|上)?訴願人等?因申請)(.|\n)*決定如下：?)',
        'maindecision':'\n主文：?\n((.|\n)*?)(\n事實：?|\n理由：?){1}',
        'fact':'主文：?\n((.|\n)*?)(\n事實：?\n){1}((.|\n)*?)\n理由：?\n', #matchres[0][3],
        'reason':'理由：?\n((.|\n)*?)(訴願審議委員會主任委員|訴願審議委員會副主任委員|訴願審議會主任)',
        'chiefdecisionmember':'(訴願審議委員會主任委員|訴願審議會主任委員|訴願審議委員會副主任委員|訴願審議會主任)\s*([\u4E00-\u9FFF\uF900-\uFAFF○]+).*\n', #matchres[0][1]
        'decisionmembers':'(?=(\n委員\s*([\u4E00-\u9FFF\uF900-\uFAFF○]+)\n))',
        }
    matchres = {}
    for key,pattern in checkItemsQueRegExp.items():
        tempmatchres = re.findall(pattern, decision_str)
        try:
            match key:
                case 'petitioner':
                    neededmatchres = [m[1:] for m in tempmatchres]
                case 'decision_made_by':
                    neededmatchres = tempmatchres[0][1]#tempmatchres[1].replace("\n","")
                case 'motivation'|'maindecision'|'reason':
                    neededmatchres = tempmatchres[0][0].replace("\n","")
                case 'fact':
                    neededmatchres = tempmatchres[0][3].replace("\n","")
                case 'chiefdecisionmember':
                    neededmatchres = tempmatchres[0][1].replace("\n","")
                case 'decisionmembers':
                    neededmatchres = [m[1].replace("\n","") for m in tempmatchres]
                case _:
                    neededmatchres = matchres
            matchres[key] = neededmatchres
        except Exception as e:
            print(f'error at {key} for {e}')
            matchres[key] = None
            #raise(e)
    return matchres

def findpattern_among_lines(patterns, lines, startingindex=0, lastfoundpos=0, debug=False):
    base_pattern = patterns[0]
    base_line = lines[startingindex]
    return_case = {}
    len_lines = len(lines)
    len_patterns = len(patterns)
    if debug:
        print(f'start matching {base_pattern}, {startingindex}: {base_line}')
    if re.search(base_pattern, base_line)!=None:
        return_case[base_pattern] = startingindex
        found = True
        lastfoundpos = startingindex
        if debug:
            print(f'found at {startingindex} established')
    else:
        found = False
    if len_patterns==1 and len_lines==startingindex+1:
        if debug:
            print(f'into len_patterns==1 and len_lines==1, {base_pattern}, startingindex{startingindex}, lastfoundpos{lastfoundpos}')
        if found==False:
            return_case[base_pattern] = not_found
            if debug:
                print(f'not_found established')
    elif len_patterns==1 and len_lines>1 and len_lines>startingindex+1:
        if debug:
            print(f'into len_patterns==1 and len_lines>1 and len_lines>startingindex+1, {base_pattern}, startingindex{startingindex}, lastfoundpos{lastfoundpos}')
        temp_search_res = findpattern_among_lines(patterns, lines, startingindex+1, lastfoundpos, debug=debug)
        return_case = merge_two_dicts(return_case, temp_search_res)
    elif len_patterns>1 and len_lines==startingindex+1:
        if debug:
            print(f'into len_patterns>1 and len_lines==1, {base_pattern}, startingindex{startingindex}, lastfoundpos{lastfoundpos}')
        if found==False:
            return_case[base_pattern] = not_found
            if debug:
                print(f'not_found established')
        return_case = merge_two_dicts(return_case, findpattern_among_lines(patterns[1:], lines, lastfoundpos+1, lastfoundpos, debug=debug))
    elif len_patterns>1 and len_lines>1 and len_lines>startingindex+1:
        if debug:
            print(f'into len_patterns>1 and len_lines>1 and len_lines>startingindex+1, {base_pattern}, startingindex{startingindex}, lastfoundpos {lastfoundpos} ')
        if found:
            startingindex_this_section = startingindex+1
            second_round_finding = findpattern_among_lines(patterns[1:], lines, startingindex_this_section, lastfoundpos, debug=debug)
        else:
            startingindex_this_section = startingindex+1
            second_round_finding = findpattern_among_lines(patterns, lines, startingindex_this_section, lastfoundpos, debug=debug)
        return_case = merge_two_dicts(return_case, second_round_finding)#, **third_round_finding}
    if debug:
        print(f'complete matching {base_pattern} and {startingindex}: {base_line}')
    return return_case

def decision_foundres_to_dict(res_pattern_pos, lines, checkItemsQue=checkItemsQueRecursive, debug=False):
    keys_pos = {key:res_pattern_pos[pattern] for key,pattern in checkItemsQue.items()}
    if debug:
        print(f'keys_pos is {keys_pos}')
    keys_e = {k:i for i,k in enumerate(keys_pos.keys())}
    if debug:
        print(f'keys_e is {keys_e}')
    e_keys = {i:k for i,k in enumerate(keys_pos.keys())}
    resdict_key_content = {}
    if debug:
        print(f'keys_pos is {keys_pos}')
    for key,pos in keys_pos.items():
        item = key.replace('_pos','')
        current_key_e = keys_e[key]
        if current_key_e+1 in e_keys:
            nextitemkey = e_keys[current_key_e+1]
            nextitempos = keys_pos[nextitemkey]
        else:
            nextitempos = -1
        match item:
            case 'petitioner'|'decision_made_by':
                try:
                    resdict_key_content[item] = lines[pos]
                    resdict_key_content[item] = resdict_key_content[item].replace('訴願人：','').replace('原處分機關：','')
                except Exception as e:
                    resdict_key_content[item] = None
            case 'motivation':
                try:
                    resdict_key_content[item] = "".join(lines[pos:nextitempos])
                except Exception as e:
                    resdict_key_content[item] = None
            case 'maindecision':
                if all_equals_to_check(keys_pos['fact_pos'], not_found):
                    nextitempos = keys_pos['reason_pos']
                resdict_key_content[item] = lines[pos+1:nextitempos]
                resdict_key_content[item] = "".join(resdict_key_content[item])
            case 'fact':
                if not all_equals_to_check(keys_pos['fact_pos'], not_found):
                    resdict_key_content[item] = lines[pos+1:nextitempos]
                    resdict_key_content[item] = "".join(resdict_key_content[item])
                else:
                    resdict_key_content[item] = None
            case 'reason':
                try:
                    resdict_key_content[item] = lines[pos+1:nextitempos]
                    resdict_key_content[item] = "".join(resdict_key_content[item])
                except Exception as e:
                    resdict_key_content[item] = None
            case 'chiefdecisionmember':
                try:
                    resdict_key_content[item] = lines[pos]
                    resdict_key_content[item] = re.sub(pattern_chief_decision_member,r'\2',resdict_key_content[item])
                except Exception as e:
                    resdict_key_content[item] = None
            case 'decisionmembers':
                pos = [p for p in pos if p!=not_found]
                try:
                    resdict_key_content[item] = [lines[p].replace('委員','') for p in pos]#lines[pos]
                except Exception as e:
                    resdict_key_content[item] = None
                    raise(e)
            case _:
                try:
                    resdict_key_content[item] = lines[pos:nextitempos]
                except Exception as e:
                    resdict_key_content[item] = None
    return resdict_key_content

def parse_decision(eypetitiondata_lines, checkItemsQue=checkItemsQueRecursive, debug=False):
    found_res = findpattern_among_lines(
        list(checkItemsQue.values()),
        eypetitiondata_lines,
        debug=debug
        )
    resdict = decision_foundres_to_dict(found_res, eypetitiondata_lines, checkItemsQue, debug=debug)
    return resdict

def parse_decision_backup(eypetitiondata_lines, checkItemsQue=checkItemsQueRecursive):
    #{'DCS_ID': '41172', 'DCS_DATE': '108/12/07', 'DCS_MASKEDSHORTREASON': '台灣世曦工程顧問股份有限公司因違反職業安全衛生法事件', 'DCS_FULLTEXT': '院臺訴字第1080196579號<br/><p>行 政 院 訴 願 決 定 書\u3000&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 院臺訴字第1080196579號</p>\r\n\r\n<p>\u3000訴願人：台灣世曦工程顧問股份有限公司</p>\r\n\r\n<p>\u3000代表人：周禮良</p>\r\n\r\n<p>\u3000訴願人因違反職業安全衛生法事件，不服勞動部107 年12月17日勞職授字第1070204953號處分，提起訴願，本院決定如下：</p>\r\n\r\n<p>\u3000\u3000主\u3000\u3000文</p>\r\n\r\n<p>訴願不受理。</p>\r\n\r\n<p>\u3000\u3000理\u3000\u3000由</p>\r\n\r\n<table class="layout">\r\n\t<tbody>\r\n\t\t<tr>\r\n\t\t\t<td valign="top" width="2%">一、</td>\r\n\t\t\t<td>按訴願法第77條第6款規定，訴願事件行政處分已不存在者，應為不受理之決定。</td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td valign="top">二、</td>\r\n\t\t\t<td>原處分機關勞動部以訴願人辦理「第C009標臺灣桃園國際機場WC滑行道遷建及雙線化工程」(以下簡稱遷建工程)之委託設計及監造技術服務案，使現場監造工程師桂君於107年8月21日早上約10時在桃園市大園區桃園機場對訴願人所監造之遷建工程位於航站北路與環場西路交叉口之污水、自來水及消防管線遷移配管地點，從事測量驗收拍照，該地點為開挖深度1.5公尺以上未設擋土支撐之露天開挖工作場所，違反營造安全衛生設施標 準第71條第1項暨職業安全衛生法第6條第1項第5款規定，經該部職業安全衛生署於107年8月21日派員實施勞動檢查時發現，依同法第43條第2款及第49條第2款規定，以107年12月17日勞職授字第1070204953號處分書處訴願人罰鍰新臺幣12萬元，並公布訴願人名稱及負責人姓名。訴願人不服，提起訴願。</td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td valign="top">三、</td>\r\n\t\t\t<td>查原處分機關經重新審查，因裁罰額度尚有審酌餘地，以108年12月2日勞職授 字第10802052241號函撤銷上開處分，有該撤銷函副本在卷可稽，是本件行政處分已不存在，訴願人所提訴願應不受理。</td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td valign="top">四、</td>\r\n\t\t\t<td>據上論結，本件訴願為不合法，依訴願法第77條第6款決定如主文。</td>\r\n\t\t</tr>\r\n\t</tbody>\r\n\t<tbody>\r\n\t</tbody>\r\n</table>\r\n\r\n<p style="text-align: right;">訴願審議委員會主任委員 林 秀 蓮<br />\r\n委員 陳 愛 娥<br />\r\n委員 陳 素 芬<br />\r\n委員 蔡 茂 寅<br />\r\n委員 郭 麗 珍<br />\r\n委員 李 寧 修<br />\r\n委員 林 春 榮<br />\r\n委員 沈 淑 妃<br />\r\n委員 黃 育 勳<br />\r\n委員 林 明 鏘</p>\r\n\r\n<p>中\u3000華\u3000民\u3000國\u3000108\u3000年\u300012\u3000月\u30004\u3000日</p>\r\n\r\n<p>如不服本決定，得於決定書送達之次日起2個月內向臺北高等行政法院提起行政訴訟。</p>\r\n', 'DCS_FILEID': None}
    elements = []
    key_cols = {'decisionmembers':[],'decisionmembers_pos':[]}
    elementi = 0
    while True:
        if elementi>=len(eypetitiondata_lines):
            break
        element = eypetitiondata_lines[elementi]
        if len(checkItemsQue)>0:
            print(f'now check item is {checkItemsQue[0]}')
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
                        print(f'檢測事實欄位結果：{elements}')
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
                case 'chiefdecisionmember_pos':
                    if re.search('(訴願審議委員會主任委員|訴願審議委員會副主任委員)',element)!=None:
                        if re.search('決定如主文。訴願審議委員會主任委員',element)!=None: #黏在一起
                            cutted_element = re.match('(.+決定如主文。)(訴願審議委員會主任委員.*)', element)
                            chiefdecisionmember = cutted_element.group(2)
                            element = cutted_element.group(1)
                            eypetitiondata_lines[elementi] = element
                            eypetitiondata_lines = eypetitiondata_lines[:elementi] + [element,chiefdecisionmember] + eypetitiondata_lines[elementi+1:]
                            elementi = elementi+1
                        key_cols['chiefdecisionmember_pos'] = elementi
                        key_cols['reason'] = "".join(elements[key_cols['reason_pos']+1:])
                        key_cols['decisionmembers_pos'].append(elementi)
                        key_cols['decisionmembers'].append(eypetitiondata_lines[elementi].replace('訴願審議委員會主任委員',''))
                        checkItemsQue = [v for v in checkItemsQue if v!='chiefdecisionmember_pos']
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