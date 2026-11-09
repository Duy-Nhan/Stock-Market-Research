import json, time, urllib.request, datetime as dt
UA={"User-Agent":"Mozilla/5.0 (personal research project)"}
def get(url, timeout=25):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except Exception as e:
        return getattr(e,"code",None), str(e)
now=int(time.time())
tz=dt.timezone(dt.timedelta(hours=7))
def fmt(t): return dt.datetime.fromtimestamp(t,tz).strftime("%Y-%m-%d %H:%M")
syms=["FPT","CMG","VCB","TCB","GAS","BSR","FUEVFVND","E1VFVN30","VNINDEX","VN30"]
print("== VNDirect dchart daily, last 400 days")
for s in syms:
    st,b=get(f"https://dchart-api.vndirect.com.vn/dchart/history?symbol={s}&resolution=D&from={now-400*86400}&to={now}")
    try:
        j=json.loads(b); n=len(j.get("t",[]))
        print(s,st,j.get("s"),n,"bars", fmt(j["t"][0]) if n else "", "->", fmt(j["t"][-1]) if n else "", "last close",j["c"][-1] if n else None,"vol",j["v"][-1] if n else None)
    except Exception as e: print(s,st,"ERR",b[:120])
print("== VNDirect intraday depth for FPT")
for res in ["1","5","15","30","60"]:
    st,b=get(f"https://dchart-api.vndirect.com.vn/dchart/history?symbol=FPT&resolution={res}&from={now-60*86400}&to={now}")
    try:
        j=json.loads(b); n=len(j.get("t",[]))
        print("res",res,st,j.get("s"),n,"bars",fmt(j["t"][0]) if n else "","->",fmt(j["t"][-1]) if n else "")
    except Exception as e: print("res",res,st,"ERR",b[:120])
print("== Yahoo .VN daily check")
for s in ["FPT","CMG","VCB","TCB","GAS","BSR","FUEVFVND","E1VFVN30"]:
    st,b=get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}.VN?interval=1d&range=1mo")
    try:
        r=json.loads(b)["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
        print(s,st,len(ts),"bars last",fmt(ts[-1]),"close",q["close"][-1],"vol",q["volume"][-1],"exch",r["meta"]["fullExchangeName"],"delay",r["meta"].get("dataGranularity"))
    except Exception as e: print(s,st,"ERR",b[:150])
