# -*- coding: utf-8 -*-
"""Baseline vat ly (depth+mag) vs ML - xem ML con cho de them gia tri khong."""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

ms = pd.read_csv("feas_mainshocks_M55.csv")
ms["time"] = pd.to_datetime(ms["time"], utc=True, format="ISO8601")
ms["year"] = ms["time"].dt.year
y = ms["any_after"].values

# feature them: lich su dia chan 30 ngay truoc (khong nhin tuong lai)
eq = pd.read_csv("data/usgs_japan_1990_2026.csv", low_memory=False)
eq["time"] = pd.to_datetime(eq["time"], utc=True, errors="coerce")
eq = eq.dropna(subset=["time","latitude","longitude","mag"]).sort_values("time")
t_all = eq["time"].values.astype("datetime64[s]").astype(np.int64)
la_a, lo_a, mg_a = eq["latitude"].values, eq["longitude"].values, eq["mag"].values
R=6371.0
def hav(a1,o1,a2,o2):
    p1,p2=np.radians(a1),np.radians(a2); dp=p2-p1; dl=np.radians(o2-o1)
    x=np.sin(dp/2)**2+np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*R*np.arcsin(np.sqrt(np.clip(x,0,1)))

n_prior=np.zeros(len(ms)); max_prior=np.zeros(len(ms))
for k in range(len(ms)):
    t0=np.datetime64(ms.loc[k,"time"].to_datetime64(),"s").astype(np.int64)
    a=np.searchsorted(t_all,t0-30*86400); b=np.searchsorted(t_all,t0)
    if b>a:
        idx=np.arange(a,b)
        d=hav(ms.loc[k,"latitude"],ms.loc[k,"longitude"],la_a[idx],lo_a[idx])
        sel=idx[d<=100]
        n_prior[k]=sel.size
        max_prior[k]=mg_a[sel].max() if sel.size else 0.0
ms["n_prior30d"]=n_prior; ms["max_mag_prior30d"]=max_prior

FEAT_PHYS = ["depth","mag"]
FEAT_FULL = ["depth","mag","latitude","longitude","n_prior30d","max_mag_prior30d"]

tr = ms["year"] <= 2015
te = ~tr
print("="*66)
print(f"TIME-SPLIT 2015   train n={tr.sum()}  test n={te.sum()}  "
      f"(duong test = {y[te].mean()*100:.1f}%)")
print("="*66)

def ev(name, model, feats):
    Xtr, Xte = ms.loc[tr, feats].values, ms.loc[te, feats].values
    model.fit(Xtr, y[tr])
    p = model.predict_proba(Xte)[:,1]
    pred = (p >= 0.5).astype(int)
    ptr = model.predict_proba(Xtr)[:,1]
    print(f"  {name:<44} AUC={roc_auc_score(y[te],p):.3f}  "
          f"PR-AUC={average_precision_score(y[te],p):.3f}  "
          f"F1={f1_score(y[te],pred):.3f}  "
          f"| train AUC={roc_auc_score(y[tr],ptr):.3f}")
    return roc_auc_score(y[te],p), roc_auc_score(y[tr],ptr)

d = DummyClassifier(strategy="most_frequent").fit(ms.loc[tr,FEAT_PHYS], y[tr])
print(f"  {'BASELINE majority (khong hoc gi)':<44} "
      f"acc={(d.predict(ms.loc[te,FEAT_PHYS])==y[te]).mean():.3f}  "
      f"AUC=0.500  F1={f1_score(y[te],d.predict(ms.loc[te,FEAT_PHYS])):.3f}")

a1,_ = ev("BASELINE VAT LY: logistic(depth, mag)",
          make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)), FEAT_PHYS)
a2,tr2 = ev("ML: gradient boosting (depth, mag)",
          HistGradientBoostingClassifier(max_depth=3, random_state=0), FEAT_PHYS)
a3,tr3 = ev("ML: gradient boosting (+ vi tri + lich su 30d)",
          HistGradientBoostingClassifier(max_depth=3, random_state=0), FEAT_FULL)

print("\n" + "="*66)
print("KET LUAN VE CHO TRONG CHO ML")
print("="*66)
print(f"  baseline vat ly (2 bien, logistic) AUC = {a1:.3f}")
print(f"  ML cung 2 bien                     AUC = {a2:.3f}   (+{a2-a1:+.3f})")
print(f"  ML day du feature                  AUC = {a3:.3f}   (+{a3-a1:+.3f})")
print(f"  overfit gap (train-test) ML day du = {tr3-a3:+.3f}")
if a3-a1 >= 0.03:
    print("  -> ML CO them gia tri thuc so voi baseline vat ly")
else:
    print("  -> ML gan nhu KHONG them gi; baseline 2 bien da du -> phai doi RQ hoac them nguon feature")
