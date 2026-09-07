"""One-time, source-grounded Telegram visual preview; never sends by default."""
from __future__ import annotations
import argparse
import json
import os
import urllib.request
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W,H=1080,1440
NAVY='#102B49'; TEAL='#007F86'; BLUE='#397CC3'; INK='#233B50'; MUTED='#506779'
PALE='#EAF4F6'; WHITE='#FFFFFF'; PAPER='#F7FAFC'; AMBER='#8A4A00'; CREAM='#FFF1DF'; RED='#9A2941'
FONT_DIR=Path('/usr/share/fonts/truetype/dejavu')
CAPTION=(
    '<b>ENK\'S MEDICAL BRIEF — visual preview</b>\n'
    'Example from the 6 September 2026 digest.\n\n'
    '<b>Can DNA testing help when a bile-duct biopsy misses malignancy?</b>\n'
    'Open the four panels in order: context → study → results → interpretation.\n\n'
    '38 patients / 47 specimens; results are <b>per biopsy</b>. Adding NGS increased '
    'sensitivity from 52% to 78%; specificity was 100% versus 96%. '
    'Small, single-centre study—not proof of improved survival or a replacement for histology.\n\n'
    '<a href="https://pubmed.ncbi.nlm.nih.gov/42698384/">PubMed</a> · '
    '<a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC13545652/">Full paper</a>\n'
    'One-time preview; your daily schedule is unchanged.'
)

def font(size:int,bold:bool=False):
    name='DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    return ImageFont.truetype(str(FONT_DIR/name),size)

class Card:
    def __init__(self,number:int,kicker:str,title:str):
        self.im=Image.new('RGB',(W,H),PAPER); self.d=ImageDraw.Draw(self.im)
        self.d.rectangle((0,0,W,16),fill=TEAL)
        self.text(56,46,"ENK'S MEDICAL BRIEF",30,True,NAVY)
        self.text(56,91,'06 SEP 2026 DIGEST  /  REQUESTED PREVIEW',19,False,MUTED)
        self.box((914,44,1024,116),PALE)
        self.text(930,57,f'{number} / 4',25,True,TEAL)
        self.text(56,156,kicker.upper(),22,True,TEAL)
        self.wrap(56,205,title,54,True,NAVY,width=968,line=66)
        self.d.line((56,1351,1024,1351),fill='#CBDCE5',width=2)
        self.text(56,1372,'Gillmeister et al. | Liver International | PMID 42698384',18,False,MUTED)
        self.text(56,1400,'Source-grounded example • Research education, not a treatment recommendation',16,False,MUTED)
    def text(self,x,y,text,size=26,bold=False,color=INK):
        self.d.text((x,y),text,font=font(size,bold),fill=color)
    def wrap(self,x,y,text,size=27,bold=False,color=INK,width=950,line=None):
        line=line or int(size*1.42)
        for para in text.split('\n'):
            row=''
            for word in para.split():
                nxt=f'{row} {word}'.strip()
                if self.d.textlength(nxt,font=font(size,bold))>width and row:
                    self.text(x,y,row,size,bold,color); y+=line; row=word
                else: row=nxt
            self.text(x,y,row,size,bold,color); y+=line
        return y
    def box(self,xy,fill=WHITE,outline=None,radius=24):
        self.d.rounded_rectangle(xy,radius=radius,fill=fill,outline=outline,width=2)
    def arrow(self,x1,y1,x2,y2,color=TEAL):
        self.d.line((x1,y1,x2,y2),fill=color,width=6)
        if y2>y1:self.d.polygon([(x2,y2),(x2-12,y2-18),(x2+12,y2-18)],fill=color)
        elif x2>x1:self.d.polygon([(x2,y2),(x2-18,y2-12),(x2-18,y2+12)],fill=color)
    def note(self,y,label,text,fill=PALE,color=TEAL,height=140):
        self.box((56,y,1024,y+height),fill)
        self.text(82,y+20,label,25,True,color)
        self.wrap(82,y+63,text,26,width=918)
    def save(self,path):self.im.save(path,'PNG',optimize=True)

def render_panels(out:Path)->list[Path]:
    out.mkdir(parents=True,exist_ok=True)
    c=Card(1,'The clinical problem','A narrowed bile duct.\nBut is it malignant?')
    c.wrap(56,366,'The question is not simply whether a duct is narrowed. It is whether the narrowing is benign or caused by malignancy.',28,width=960)
    c.box((308,507,772,588),NAVY); c.text(362,530,'BILE-DUCT STRICTURE',27,True,WHITE)
    c.d.line((540,590,540,620),fill=TEAL,width=5)
    c.d.line((278,620,802,620),fill=TEAL,width=5)
    c.arrow(278,620,278,653); c.arrow(802,620,802,653)
    c.box((56,659,500,776),PALE); c.box((580,659,1024,776),'#F8E9EC')
    c.text(88,681,'BENIGN',31,True,TEAL); c.text(612,681,'MALIGNANT',31,True,RED)
    c.text(88,731,'Non-cancerous narrowing',23); c.text(612,731,'Cancer-related narrowing',23)
    c.note(815,'Why a biopsy may not settle the question','Histology can miss malignancy in this setting. A negative result may leave diagnostic uncertainty.',CREAM,AMBER,159)
    c.box((56,1008,498,1158),WHITE); c.box((582,1008,1024,1158),WHITE)
    c.text(82,1030,'HISTOLOGY',28,True,BLUE); c.text(608,1030,'NGS',28,True,TEAL)
    c.wrap(82,1076,'Cell appearance and tissue architecture',25,width=389)
    c.wrap(608,1076,'Cancer-associated DNA alterations',25,width=389)
    c.text(523,1050,'+',45,True,TEAL)
    c.note(1192,'The research question','Can adding next-generation sequencing (NGS) identify malignant strictures missed by histology?',height=136)
    paths=[out/'01-context.png'];c.save(paths[-1])

    c=Card(2,'The experiment','One cohort.\nThree diagnostic approaches.')
    c.box((56,370,450,510),PALE);c.box((630,370,1024,510),PALE)
    c.text(82,383,'38',66,True,NAVY);c.text(211,410,'patients',32,True,NAVY)
    c.text(82,466,'Unexplained biliary strictures',22)
    c.arrow(475,440,605,440)
    c.text(656,383,'47',66,True,NAVY);c.text(785,410,'biopsies',32,True,NAVY)
    c.text(656,466,'Some patients sampled again',22)
    c.text(56,544,'ONE CENTRE  •  Dresden, Germany  •  2019–2023',25,True,TEAL)
    c.text(56,606,'Same specimens were evaluated using:',28,True,NAVY)
    for x,label,desc in [(56,'Histology','Appearance of\ncells and tissue'),(386,'NGS','DNA from FFPE\nbiopsy tissue'),(716,'Combined','Morphological +\nmolecular findings')]:
        c.box((x,667,x+308,834),WHITE)
        c.text(x+22,689,label,31,True,TEAL)
        c.wrap(x+22,743,desc,24,width=264,line=34)
        c.arrow(x+154,851,x+154,890)
    c.box((56,912,1024,1097),NAVY)
    c.text(84,934,'COMPARED WITH FINAL DIAGNOSIS',27,True,WHITE)
    c.wrap(84,985,'Histological confirmation of malignancy OR imaging follow-up without malignant progression for at least 6 months.',27,color=WHITE,width=912)
    c.note(1131,'23 of 47 specimens were classified as malignant','Results are PER BIOPSY—not per patient. This was a diagnostic comparison, not a randomised treatment trial.',CREAM,AMBER,184)
    paths.append(out/'02-study.png');c.save(paths[-1])

    c=Card(3,'The results','More malignancy detected.\nStill not every case.')
    def chart(y,title,explanation,values):
        c.text(56,y,title,32,True,NAVY)
        c.text(56,y+48,explanation,22,False,MUTED)
        left=364;right=904;top=y+98
        for tick in [0,25,50,75,100]:
            x=left+(right-left)*tick/100
            c.d.line((x,top-5,x,top+175),fill='#D6E3E9',width=2)
            c.text(x-14,top+184,str(tick),18,False,MUTED)
        for i,(label,value,color) in enumerate(zip(['Histology alone','NGS alone','Histology + NGS'],values,[BLUE,TEAL,NAVY])):
            yy=top+i*59
            c.text(56,yy+5,label,25,True,INK)
            c.d.rounded_rectangle((left,yy,left+(right-left)*value/100,yy+39),radius=7,fill=color)
            c.text(left+(right-left)*value/100+14,yy+3,f'{value}%',25,True,color)
    chart(365,'SENSITIVITY','Malignant specimens correctly identified (%)',[52,65,78])
    chart(715,'SPECIFICITY','Benign specimens correctly identified as negative (%)',[100,96,96])
    c.box((56,1080,510,1231),PALE);c.box((538,1080,1024,1231),CREAM)
    c.text(82,1094,'+26',52,True,TEAL);c.text(231,1118,'percentage points',21,True,TEAL)
    c.wrap(82,1167,'Sensitivity: 52% → 78%',25,width=404)
    c.text(564,1094,'~22%',52,True,AMBER)
    c.wrap(564,1167,'Malignant specimens still missed',23,width=418,line=31)
    c.wrap(56,1260,'Biopsy-level point estimates • Small sample • NGS excludes variants of uncertain significance (VUS). Specificity: 100% → 96%.',23,width=957,line=31)
    paths.append(out/'03-results.png');c.save(paths[-1])

    c=Card(4,'Interpretation and limitations','An addition to histology.\nNot a replacement.')
    c.box((56,371,1024,511),NAVY)
    c.text(84,391,'MORPHOLOGY   +   MOLECULAR FINDINGS',30,True,WHITE)
    c.text(84,450,'Two types of information, interpreted together.',27,False,WHITE)
    c.box((56,552,1024,709),PALE)
    c.text(82,575,'WHAT THIS SUPPORTS',26,True,TEAL)
    c.wrap(82,622,'Adding NGS may detect malignant strictures that histology alone misses in a similar clinical setting.',27,width=914)
    c.box((56,742,1024,895),'#F8E9EC')
    c.text(82,765,'WHAT THIS DOES NOT ESTABLISH',26,True,RED)
    c.wrap(82,812,'A replacement for histology. Exclusion of every cancer. Improved survival or cost-effectiveness.',27,width=914)
    c.text(56,928,'WHY THE RESULT NEEDS CAUTION',28,True,NAVY)
    for y,n,title,detail in [(982,'01','Small, single-centre cohort','38 patients; results may differ elsewhere.'),(1072,'02','Repeat biopsies','47 specimens are not 47 independent patients.'),(1162,'03','Limited follow-up','Some initially benign cases may need longer follow-up.')]:
        c.box((56,y,116,y+63),CREAM,radius=14);c.text(67,y+16,n,25,True,AMBER)
        c.text(141,y,title,27,True,NAVY);c.text(141,y+41,detail,23)
    c.text(56,1280,'PROMISING ADJUNCTIVE EVIDENCE — NOT A NEW STANDARD BY ITSELF',21,True,TEAL)
    paths.append(out/'04-interpretation.png');c.save(paths[-1])
    return paths

def make_payload(chat_id:str,paths:list[Path])->tuple[bytes,str]:
    if len(paths)!=4:raise ValueError('Exactly four panels are required')
    boundary='----medicalbrief'+uuid.uuid4().hex
    chunks=[]
    def field(name:str,value:bytes,filename:str|None=None):
        chunks.append(f'--{boundary}\r\n'.encode())
        disposition=f'Content-Disposition: form-data; name="{name}"'
        if filename:disposition+=f'; filename="{filename}"'
        chunks.append((disposition+'\r\n').encode())
        if filename:chunks.append(b'Content-Type: image/png\r\n')
        chunks.append(b'\r\n'+value+b'\r\n')
    media=[{'type':'photo','media':f'attach://panel{i}'} for i in range(4)]
    media[0].update(caption=CAPTION,parse_mode='HTML')
    field('chat_id',chat_id.encode())
    field('media',json.dumps(media,ensure_ascii=False).encode())
    for i,path in enumerate(paths):field(f'panel{i}',path.read_bytes(),path.name)
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks),f'multipart/form-data; boundary={boundary}'

def validate_response(response:dict,chat_id:str)->dict:
    result=response.get('result')
    if response.get('ok') is not True or not isinstance(result,list) or len(result)!=4:
        raise RuntimeError('Telegram did not confirm acceptance of all four images; do not automatically retry.')
    if len({r.get('media_group_id') for r in result})!=1 or not result[0].get('media_group_id'):
        raise RuntimeError('Telegram album grouping was not confirmed.')
    for r in result:
        if 'message_id' not in r or str(r.get('chat',{}).get('id'))!=chat_id.strip():
            raise RuntimeError('Telegram recipient or message confirmation did not match.')
    return {'telegram_ok':True,'accepted_images':4,'recipient_matches':True,'message_ids':[r['message_id'] for r in result]}

def send_album(token:str,chat_id:str,paths:list[Path])->dict:
    if not token or not chat_id:raise RuntimeError('Required Telegram repository secrets are missing.')
    body,content_type=make_payload(chat_id,paths)
    req=urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMediaGroup',data=body,headers={'Content-Type':content_type},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=60) as response:
            data=json.loads(response.read().decode())
    except Exception:
        raise RuntimeError('Telegram send was not confirmed. No automatic retry: delivery could be ambiguous. Credentials are redacted.') from None
    return validate_response(data,chat_id)

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument('--send',action='store_true');parser.add_argument('--output',type=Path,default=Path('preview-output'));args=parser.parse_args()
    paths=render_panels(args.output)
    (args.output/'caption.html').write_text(CAPTION,encoding='utf-8')
    print(f'Rendered {len(paths)} panels. Sending is opt-in.')
    if args.send:
        if os.environ.get('GITHUB_RUN_ATTEMPT','1')!='1':raise RuntimeError('Refusing workflow rerun to prevent duplicate delivery.')
        receipt=send_album(os.environ.get('TELEGRAM_BOT_TOKEN',''),os.environ.get('TELEGRAM_CHAT_ID',''),paths)
        (args.output/'receipt.json').write_text(json.dumps(receipt),encoding='utf-8')
        print('TELEGRAM_ACCEPTED '+json.dumps(receipt))
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('## Telegram preview\nFour-image album accepted by Telegram; recipient matched configured chat.\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
