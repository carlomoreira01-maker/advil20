"""Releituras locais de regiões densas. Originais e leitura principal são preservados."""
from statistics import median
import subprocess
from PIL import Image


def collect_regions(image,words,recognize):
    from engine_v2 import group_lines
    from tiss_geometry import anchors
    page={'number':1,'size':list(image.size),'lines':group_lines(words)}
    aa=anchors(page)
    small=[a['height'] for a in aa if a['num'] in [2,8,9,10,15,16,17,25,26]]
    if len(small)<4 or image.width/max(1,median(small))<120:return []
    beneficiary=min((a['y'] for a in aa if a['num'] in [8,9,10]),default=None)
    table=min((a['y'] for a in aa if a['num'] in [25,26]),default=None)
    if beneficiary is None or table is None:return []
    doctor=min((a['y'] for a in aa if a['num'] in [13,14,15,16,17] and a['y']>beneficiary+image.height*.01),default=(beneficiary+table)/2)
    end=min((a['y'] for a in aa if a['num'] in [29,30,31,36,40,41] and a['y']>table+median(small)),default=min(image.height,table+image.height*.2))
    h=median(small)
    bands=[('header',(0,0,image.width,beneficiary-h*.5),[2,3,4,5,6,7],[(6,2),(11,2),(4,1.5)]),
           ('beneficiary',(0,beneficiary-h*1.3,image.width,doctor-h*.35),[8,9,10],[(6,2),(11,2),(4,1.5),(6,1.5)]),
           ('doctor',(0,doctor-h*1.1,image.width,table-h*.5),[13,15,16,17,18,19,22],[(6,2),(11,2),(4,1.5),(11,1.5)]),
           ('table',(0,table-h,image.width,end-h*.5),[],[(6,2),(4,1.5),(6,1.5)])]
    result=[]
    for family,box,targets,settings in bands:
        box=(max(0,round(box[0])),max(0,round(box[1])),min(image.width,round(box[2])),min(image.height,round(box[3])))
        if box[3]-box[1]<8:continue
        crop=image.crop(box)
        for psm,scale in settings:
            try:
                read=recognize(crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS),psm)
            except (OSError,ValueError,subprocess.TimeoutExpired):
                if words:words[0].setdefault('regional_warnings',[]).append('Uma releitura regional falhou; conferir os campos no original.')
                continue
            for word in read:
                word['box']=[v/scale+box[i%2] for i,v in enumerate(word['box'])]
                word.update(regional_reading=family+'-'+str(psm)+'-'+str(scale),regional_family=family,regional_targets=targets,
                            regional_bounds=list(box))
            result.extend(read)
    return result
