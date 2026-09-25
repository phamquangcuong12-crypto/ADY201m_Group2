# -*- coding: utf-8 -*-
import numpy as np, pandas as pd
from pathlib import Path
R=6371.0
def hav(a1,o1,a2,o2):
    p1,p2=np.radians(a1),np.radians(a2); dp=p2-p1; dl=np.radians(o2-o1)
    x=np.sin(dp/2)**2+np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*R*np.arcsin(np.sqrt(np.clip(x,0,1)))
def gkw(m):
    return 10**(0.1238*m+0.983), np.where(m>=6.5,10**(0.032*m+2.7389),10**(0.5409*m-0.547))

eq=pd.read_csv("data/usgs_japan_1990_2026.csv",low_memory=False)
eq["time"]=pd.to_datetime(eq["time"],utc=True,errors="coerce")
eq=eq.dropna(subset=["time","latitude","longitude","mag","depth"]).sort_values("time").reset_index(drop=True)
Mc=4.6
cat=eq[eq["mag"]>=Mc].reset_index(drop=True)
t=cat["time"].values.astype("datetime64[s]").astype(np.int64)
la,lo,mg,dp=cat["latitude"].values,cat["longitude"].values,cat["mag"].values,cat["depth"].values
n=len(cat); clu=np.full(n,-1,np.int64); cid=0
for i in np.argsort(-mg):
    if clu[i]!=-1: continue
    dk,td=gkw(mg[i]); a=np.searchsorted(t,t[i]); b=np.searchsorted(t,t[i]+int(td*86400))
    if b<=a+1: continue
    idx=np.arange(a,b); idx=idx[(clu[idx]==-1)&(mg[idx]<mg[i])&(idx!=i)]
    if idx.size==0: continue
    hit=idx[hav(la[i],lo[i],la[idx],lo[idx])<=dk]
    if hit.size: clu[hit]=cid; cid+=1
main=cat[clu==-1].reset_index(drop=True)

MS=5.5
ms=main[main["mag"]>=MS].reset_index(drop=True)
cnt=np.zeros(len(ms),np.int64)
for k in range(len(ms)):
    t0=np.datetime64(ms.loc[k,"time"].to_datetime64(),"s").astype(np.int64)
    a=np.searchsorted(t,t0); b=np.searchsorted(t,t0+86400)
    if b<=a: continue
    idx=np.arange(a,b)
    cnt[k]=int(((hav(ms.loc[k,"latitude"],ms.loc[k,"longitude"],la[idx],lo[idx])<=100)&(mg[idx]<ms.loc[k,"mag"])).sum())
ms["n_after24h"]=cnt; ms["any_after"]=(cnt>0).astype(int)

print("="*64); print(f"IS THERE A LEARNABLE SIGNAL?  (mainshock M>={MS}, n={len(ms)})"); print("="*64)

print("\n-- Depth vs aftershock productivity (main physical hypothesis) --")
ms["depth_bin"]=pd.cut(ms["depth"],[0,30,70,150,300,700],
    labels=["0-30 (crustal)","30-70","70-150","150-300","300-700 (deep)"])
g=ms.groupby("depth_bin",observed=True).agg(n=("n_after24h","size"),
    pct_with_aftershock=("any_after","mean"),mean=("n_after24h","mean"),
    median=("n_after24h","median"))
g["pct_with_aftershock"]=(g["pct_with_aftershock"]*100).round(1)
print(g.round(2).to_string())

print("\n-- Magnitude vs productivity --")
ms["mag_bin"]=pd.cut(ms["mag"],[5.5,6.0,6.5,7.0,9.5],labels=["5.5-6.0","6.0-6.5","6.5-7.0","7.0+"],right=False)
g2=ms.groupby("mag_bin",observed=True).agg(n=("n_after24h","size"),
    pct_with_aftershock=("any_after","mean"),mean=("n_after24h","mean"))
g2["pct_with_aftershock"]=(g2["pct_with_aftershock"]*100).round(1)
print(g2.round(2).to_string())

print("\n-- Test: shallow (<70km) vs deep (>=70km) --")
from scipy import stats
sh=ms[ms["depth"]<70]["any_after"]; de=ms[ms["depth"]>=70]["any_after"]
print(f"  shallow: {sh.mean()*100:.1f}% with aftershock (n={len(sh)})")
print(f"  deep   : {de.mean()*100:.1f}% with aftershock (n={len(de)})")
ct=np.array([[sh.sum(),len(sh)-sh.sum()],[de.sum(),len(de)-de.sum()]])
chi2,p,_,_=stats.chi2_contingency(ct)
print(f"  chi-square p = {p:.3e}  {'<- signal PRESENT' if p<0.05 else '<- NO signal'}")

print("\n-- Does Tohoku 2011 dominate? --")
ms["year"]=ms["time"].dt.year
top=ms.nlargest(8,"n_after24h")[["time","mag","depth","n_after24h","place"]]
top["time"]=top["time"].dt.strftime("%Y-%m-%d %H:%M")
print(top.to_string(index=False))
y2011=ms[ms["year"]==2011]
print(f"\n  2011 sequences  : {len(y2011)}/{len(ms)} = {len(y2011)/len(ms)*100:.1f}% of sequences")
print(f"  2011 aftershocks: {y2011['n_after24h'].sum():,}/{ms['n_after24h'].sum():,} = "
      f"{y2011['n_after24h'].sum()/ms['n_after24h'].sum()*100:.1f}% of all aftershocks")
ex=ms[ms["year"]!=2011]
print(f"  WITHOUT 2011: n={len(ex)}, share with aftershock={ex['any_after'].mean()*100:.1f}%, "
      f"mean={ex['n_after24h'].mean():.2f}")

print("\n-- BASELINE for the binary task 'at least 1 aftershock within 24h' --")
for th in [5.0,5.5,6.0]:
    s=main[main["mag"]>=th].reset_index(drop=True)
    c=np.zeros(len(s),np.int64)
    for k in range(len(s)):
        t0=np.datetime64(s.loc[k,"time"].to_datetime64(),"s").astype(np.int64)
        a=np.searchsorted(t,t0); b=np.searchsorted(t,t0+86400)
        if b>a:
            idx=np.arange(a,b)
            c[k]=int(((hav(s.loc[k,"latitude"],s.loc[k,"longitude"],la[idx],lo[idx])<=100)&(mg[idx]<s.loc[k,"mag"])).sum())
    y=(c>0).astype(int)
    maj=max(y.mean(),1-y.mean())
    print(f"  M>={th}: n={len(s):>5,}  positive={y.mean()*100:>5.1f}%  majority baseline={maj*100:>5.1f}%")
ms.to_csv("feas_mainshocks_M55.csv",index=False)
print("\nsaved feas_mainshocks_M55.csv")
