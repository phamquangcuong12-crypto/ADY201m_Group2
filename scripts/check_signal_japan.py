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

print("="*64); print(f"TIN HIEU HOC DUOC?  (mainshock M>={MS}, n={len(ms)})"); print("="*64)

print("\n-- Do sau vs nang suat du chan (gia thuyet vat ly chinh) --")
ms["depth_bin"]=pd.cut(ms["depth"],[0,30,70,150,300,700],
    labels=["0-30 (vo)","30-70","70-150","150-300","300-700 (sau)"])
g=ms.groupby("depth_bin",observed=True).agg(n=("n_after24h","size"),
    ty_le_co_du_chan=("any_after","mean"),trung_binh=("n_after24h","mean"),
    trung_vi=("n_after24h","median"))
g["ty_le_co_du_chan"]=(g["ty_le_co_du_chan"]*100).round(1)
print(g.round(2).to_string())

print("\n-- Magnitude vs nang suat --")
ms["mag_bin"]=pd.cut(ms["mag"],[5.5,6.0,6.5,7.0,9.5],labels=["5.5-6.0","6.0-6.5","6.5-7.0","7.0+"],right=False)
g2=ms.groupby("mag_bin",observed=True).agg(n=("n_after24h","size"),
    ty_le_co_du_chan=("any_after","mean"),trung_binh=("n_after24h","mean"))
g2["ty_le_co_du_chan"]=(g2["ty_le_co_du_chan"]*100).round(1)
print(g2.round(2).to_string())

print("\n-- Kiem dinh: nong (<70km) vs sau (>=70km) --")
from scipy import stats
sh=ms[ms["depth"]<70]["any_after"]; de=ms[ms["depth"]>=70]["any_after"]
print(f"  nong: {sh.mean()*100:.1f}% co du chan (n={len(sh)})")
print(f"  sau : {de.mean()*100:.1f}% co du chan (n={len(de)})")
ct=np.array([[sh.sum(),len(sh)-sh.sum()],[de.sum(),len(de)-de.sum()]])
chi2,p,_,_=stats.chi2_contingency(ct)
print(f"  chi-square p = {p:.3e}  {'<- CO tin hieu' if p<0.05 else '<- KHONG'}")

print("\n-- Tohoku 2011 co lan at khong? --")
ms["year"]=ms["time"].dt.year
top=ms.nlargest(8,"n_after24h")[["time","mag","depth","n_after24h","place"]]
top["time"]=top["time"].dt.strftime("%Y-%m-%d %H:%M")
print(top.to_string(index=False))
y2011=ms[ms["year"]==2011]
print(f"\n  chuoi nam 2011 : {len(y2011)}/{len(ms)} = {len(y2011)/len(ms)*100:.1f}% so chuoi")
print(f"  du chan nam 2011: {y2011['n_after24h'].sum():,}/{ms['n_after24h'].sum():,} = "
      f"{y2011['n_after24h'].sum()/ms['n_after24h'].sum()*100:.1f}% tong du chan")
ex=ms[ms["year"]!=2011]
print(f"  BO 2011 di: n={len(ex)}, ty le co du chan={ex['any_after'].mean()*100:.1f}%, "
      f"trung binh={ex['n_after24h'].mean():.2f}")

print("\n-- BASELINE cho bai phan loai nhi phan 'co >=1 du chan trong 24h' --")
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
    print(f"  M>={th}: n={len(s):>5,}  duong={y.mean()*100:>5.1f}%  baseline majority={maj*100:>5.1f}%")
ms.to_csv("feas_mainshocks_M55.csv",index=False)
print("\nda luu feas_mainshocks_M55.csv")
