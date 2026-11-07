"""Orientação, contraste e inclinação locais; coordenadas sempre recuperáveis no original."""
import math
from PIL import Image, ImageOps, ImageFilter
from core import norm


def union_box(words, original=True):
    boxes=[w.get('original_box',w['box']) if original else w['box'] for w in words]
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else None


def source_box(line):
    return union_box(line.get('words',[])) or line['box']


def projection_score(image):
    data=image.tobytes();width=image.width
    rows=[data[i:i+width].count(0) for i in range(0,len(data),width)]
    return sum((a-b)**2 for a,b in zip(rows,rows[1:]))


def deskew_angle(image):
    small=image.copy();small.thumbnail((900,900))
    mask=small.point(lambda v:0 if v<170 else 255)
    if mask.getextrema()==(255,255):return 0.0
    scores=[(projection_score(mask.rotate(a,resample=Image.Resampling.NEAREST,fillcolor=255)),a)
            for a in [i*.5 for i in range(-8,9)]]
    best,angle=max(scores)
    baseline=next(s for s,a in scores if a==0)
    return angle if best>baseline*1.12 else 0.0


def recognize_page(image, recognize):
    image=ImageOps.exif_transpose(image).convert('L')
    original_size=image.size
    image=ImageOps.autocontrast(image,cutoff=1)
    if image.getextrema()==(255,255):return []
    probe=image.copy();probe.thumbnail((1800,1800))
    candidates=[]
    anchors={'PACIENTE','NOME','BENEFICIARIO','GUIA','EXAMES','HEMOGRAMA','SOLICITANTE','AUTORIZACAO','NASCIMENTO','CODIGO'}
    for angle in [0,90,180,270]:
        words=recognize(probe.rotate(angle,expand=True),6)
        tokens=[norm(w['text']).strip(':.') for w in words]
        # Ruling lines sometimes become a single thousands-character TSV token.
        # Its length is not evidence that the page is upright.
        score=sum(min(16,len(w['text']))*max(0,w['confidence']-45) for w in words
                  if 1<=len(w['text'])<=40 and sum(c.isalnum() for c in w['text'])>=len(w['text'])*.65)
        score+=sum(600 for t in tokens if t in anchors)
        candidates.append((score,angle))
        if angle==0 and sum(t in anchors for t in tokens)>=3 and words and sum(w['confidence'] for w in words)/len(words)>85:
            break
    angle=max(candidates,key=lambda item:item[0])[1]
    upright=image.rotate(angle,expand=True)
    skew=deskew_angle(upright)
    corrected=upright.rotate(skew,resample=Image.Resampling.BICUBIC,fillcolor=255)
    factor=min(2.0,max(1.0,1600/max(1,corrected.width)))
    if factor!=1:corrected=corrected.resize((round(corrected.width*factor),round(corrected.height*factor)),Image.Resampling.LANCZOS)
    corrected=corrected.filter(ImageFilter.UnsharpMask(radius=1.2,percent=130,threshold=3))
    words=recognize(corrected,3)
    # Automatic page segmentation can omit isolated digits at the bottom of a
    # table. A second LOCAL reading supplies only spatially missing words, never
    # a default quantity and never a value copied from another row/column.
    if any(norm(w['text']).strip('.:') in {'CODIGO','DESCRICAO','QTD','QTDE'} for w in words):
        supplemental=recognize(corrected,6)
        for word in supplemental:
            if word['confidence']<70:continue
            b=word['box']
            overlap=False
            for existing in words:
                e=existing['box'];intersection=max(0,min(b[2],e[2])-max(b[0],e[0]))*max(0,min(b[3],e[3])-max(b[1],e[1]))
                area=min((b[2]-b[0])*(b[3]-b[1]),(e[2]-e[0])*(e[3]-e[1]))
                if area and intersection/area>.4:overlap=True;break
            if not overlap:words.append(word)
    from ocr_regions import collect_regions
    words.extend(collect_regions(corrected,words,recognize))
    width,height=original_size;cx,cy=upright.width/2,upright.height/2
    rad=math.radians(skew);c,s=math.cos(rad),math.sin(rad)
    def inverse(x,y):
        dx,dy=x-cx,y-cy;x,y=cx+c*dx-s*dy,cy+s*dx+c*dy
        if angle==90:x,y=width-y,x
        elif angle==180:x,y=width-x,height-y
        elif angle==270:x,y=y,height-x
        return max(0,min(width,x)),max(0,min(height,y))
    for w in words:
        w['box']=[v/factor for v in w['box']]
        if w.get('regional_bounds'):w['regional_bounds']=[v/factor for v in w['regional_bounds']]
        x0,y0,x1,y1=w['box'];points=[inverse(x,y) for x in [x0,x1] for y in [y0,y1]]
        w['original_box']=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
        w['orientation']=angle;w['deskew']=skew
    return words
