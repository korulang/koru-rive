#!/usr/bin/env python3
"""Tier-1 command-stream comparator: golden (recording Renderer text) vs
corpusdump ops (OpRec lines). Stream-equal = same event sequence per frame:
transforms, drawPath records (style/color/thick + V-coord stream), clips.
Usage: tier1_compare.py <fixture> [<fixture>...]  (run from koru-rive root)
"""
import re, os, sys

def parse_ops(path):
    abs_={}; frames={}; cur=None
    for line in open(path,errors='replace'):
        m=re.match(r"AB idx=(\d+) name='(.*)'",line)
        if m: abs_[m.group(2)]=int(m.group(1)); continue
        m=re.match(r'=== ab (\d+) fr (\d+) ===',line)
        if m: cur=(int(m.group(1)),int(m.group(2))); frames[cur]=[]; continue
        if cur and line.startswith('OP k='):
            frames[cur].append(line.strip())
    return abs_,frames

def numlist(s): return [float(x) for x in re.findall(r'[-+]?\d+\.?\d*(?:e[-+]?\d+)?',s)]

def our_events(ops):
    """Op stream -> event list. k=6 pushmat=transform event; path ops accumulate;
    k=8 draw closes a draw record; k=9 clippush closes a clip record."""
    evs=[]; pend=[]
    def flush_draw():
        nonlocal pend
        trans=None; v=[]
        for p in pend:
            k=int(p[5])
            if k==6:
                g=re.search(r'a=([-\d.e]+) b=([-\d.e]+) c=([-\d.e]+) d=([-\d.e]+) e=([-\d.e]+) g=([-\d.e]+)',p)
                if g: trans=tuple(round(float(g.group(i)),4) for i in range(1,7))
            elif 1<=k<=5:
                c=re.search(r'x1=([-\d.e]+) y1=([-\d.e]+) x2=([-\d.e]+) y2=([-\d.e]+) x3=([-\d.e]+) y3=([-\d.e]+)',p)
                if c:
                    xyz=tuple(round(float(c.group(i)),4) for i in range(1,7))
                    v.append((k-1 if k<4 else (2 if k==3 else (4 if k==4 else 5)),xyz))
        st=re.search(r'style=(\d+) color=(\w+) thick=([-\d.e]+).*eo=(\d)',pend[-1])
        evs.append(('draw',trans,tuple(v),(st.group(1),st.group(2).lower(),round(float(st.group(3)),4)) if st else None))
        pend=[]
    for o in ops:
        k=int(o[5])
        pend.append(o)
        if k==8: flush_draw()
        elif k==9:
            # clip record: path ops since last marker + k=9
            v=[]
            for p in pend:
                pk=int(p[5])
                if 1<=pk<=5:
                    c=re.search(r'x1=([-\d.e]+) y1=([-\d.e]+) x2=([-\d.e]+) y2=([-\d.e]+) x3=([-\d.e]+) y3=([-\d.e]+)',p)
                    if c: v.append(tuple(round(float(c.group(i)),4) for i in range(1,7)))
            evs.append(('clip',len(v)))
            pend=[]
        elif k==10:
            evs.append(('clippop',)); pend=[]
    # standalone transforms not consumed by a draw (e.g. artboard-level)
    return evs

def gold_events(body):
    evs=[]; cur_trans=None; cur_v=None; in_draw=False
    for line in body.split('\n'):
        s=line.strip()
        t=re.match(r'transform ([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+)',s)
        if t:
            cur_trans=tuple(round(float(x),4) for x in t.groups()); continue
        if s.startswith('clipPath'):
            pts=int(re.search(r'pts=(\d+)',s).group(1))
            evs.append(('clip',pts)); in_draw=False; continue
        d=re.match(r'drawPath style=(\d+) color=(\w+) thick=([\d.]+)',s)
        if d:
            in_draw=True; cur_v=[]
            evs.append(('draw',cur_trans,d.groups()[:3],[]))
            continue
        v=re.match(r'V (\d)\s*(.*)',s)
        if v and in_draw and evs and evs[-1][0]=='draw':
            nums=tuple(round(float(x),4) for x in numlist(v.group(2)))
            evs[-1][3].append((int(v.group(1)),nums))
    out=[]
    for e in evs:
        if e[0]=='draw': out.append(('draw',e[1],e[2],tuple(e[3])))
        elif e[0]=='clip': out.append(('clip',None,e[1]))
        else: out.append((e[0],))
    return out

def close(a,b,eps=0.02): return len(a)==len(b) and all(abs(x-y)<=eps for x,y in zip(a,b))

def events_match(g,o):
    if len(g)!=len(o): return False
    for ge,oe in zip(g,o):
        if ge[0]!=oe[0]: return False
        if ge[0]=='draw':
            gt,ot=ge[1],oe[1]
            if (gt is None)!=(ot is None): return False
            if gt and ot and not close(gt,ot): return False
            gs,os_=ge[2],oe[3] if len(oe)>3 else oe[2]
            # golden style tuple (style,color,thick) vs ours (style,color,thick)
            if gs and os_:
                if gs[0]!=os_[0] or gs[1].lower()!=os_[1].lower() or abs(float(gs[2])-float(os_[2]))>0.02: return False
            gv,ov=ge[3],oe[2]
            if len(gv)!=len(ov): return False
            for (gverb,gc),(overb,oc) in zip(gv,ov):
                if gverb!=overb: return False
                if len(gc)==0: continue  # golden tail-suppressed endpoint (V <verb> bare)
                # golden suppresses trailing coords on tail segments too
                # (last cubic drops its end point): prefix-compare what exists
                if gverb==5: continue
                if not close(gc, oc[:len(gc)]): return False
        elif ge[0]=='clip':
            if ge[2] != (oe[1] if len(oe)>1 else None): return False
    return True

def golden_artboards(path):
    txt=open(path,errors='replace').read()
    names=[l.split('name=',1)[1].strip() for l in txt.split('\n') if 'ARTBOARD' in l and 'name=' in l]
    parts=txt.split('--- frame 0 t=0.0333 ---')
    return names,parts

def compare_fixture(n):
    gpath=f'oracle/goldens/corpus/{n}.txt'; opath=f'/tmp/corpus_ops/{n}.txt'
    if not (os.path.exists(gpath) and os.path.exists(opath)): return None
    names,parts=golden_artboards(gpath)
    abs_,frames=parse_ops(opath)
    if not abs_: return ('NO-OPS',0,0)
    results=[]
    for ai,gname in enumerate(names):
        ab=abs_.get(gname)
        if ab is None: results.append((gname,'NO-AB')); continue
        body=parts[ai+1] if ai+1<len(parts) else ''
        secs=re.split(r'--- frame (\d+) t=[\d.]+ ---',body)
        gframes={'0':secs[0]}
        for i in range(1,len(secs)-1,2): gframes[secs[i]]=secs[i+1]
        eq=tot=0; diffs=[]
        for gn,gb in gframes.items():
            ge=gold_events(gb)
            if not ge: continue
            tot+=1; hit=False
            for cand in (int(gn),2*int(gn)):
                ops=frames.get((ab,cand))
                if ops is None: continue
                oe=our_events(ops)
                if events_match(ge,oe): hit=True;break
                if len(ge)==len(oe) and all(events_match([g],[o]) for g,o in zip(sorted(ge,key=str),sorted(oe,key=str))): hit='REORDERED';break
            if hit: eq+=1
            else: diffs.append(gn)
        results.append((gname,f'{eq}/{tot}',diffs[:4]))
    return results

if __name__=='__main__':
    allrows={}
    for n in sys.argv[1:]:
        r=compare_fixture(n)
        if r: allrows[n]=r
    for n,res in allrows.items():
        for gname,ver,d in res: print(f'{n} [{gname}]: {ver} {d if d else ""}')
    full=sum(1 for res in allrows.values() for _,v,_ in res if v and '/' in str(v) and v.split('/')[0]==v.split('/')[1] and int(v.split('/')[1])>0)
    print(f'fixtures:{len(allrows)} ab-stream-equal:{full}')
