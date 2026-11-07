"""Rotação apenas da visualização; caixas continuam referenciando o original."""

def rotated_box(box,size,angle):
    if box is None:return None
    width,height=size;angle=int(angle)%360
    def point(x,y):
        if angle==90:return y,width-x
        if angle==180:return width-x,height-y
        if angle==270:return height-y,x
        return x,y
    x0,y0,x1,y1=box;points=[point(x,y) for x in [x0,x1] for y in [y0,y1]]
    return [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
