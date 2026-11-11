"""Source transport only; uniform incumbent source blocks, never gold boundaries."""
from tools.fresh_retrieval_evaluation import windows
from html.parser import HTMLParser
import re

class Body(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.depth=0;self.active=False;self.out=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if attrs.get('role')=='main':self.active=True;self.depth=1;return
        if self.active:
            if tag not in ('br','hr','img','input','meta','link','wbr'):self.depth+=1
            if tag in ('p','div','h1','h2','h3','h4','li','pre','dt','dd','tr','br'):self.out.append('\n')
    def handle_endtag(self,tag):
        if self.active:
            if tag in ('p','div','h1','h2','h3','h4','li','pre','dt','dd','tr'):self.out.append('\n')
            self.depth-=1
            if self.depth==0:self.active=False
    def handle_data(self,data):
        if self.active:self.out.append(data)

def extract(raw):
    parser=Body();parser.feed(raw.decode('utf8'))
    text=''.join(parser.out).replace('\r\n','\n')
    text=re.sub(r'[ \t]+',' ',text)
    return re.sub(r'\n{3,}','\n\n',text).strip()

def blocks(source,text):
    return windows(source,text,width=1800,stride=900)
