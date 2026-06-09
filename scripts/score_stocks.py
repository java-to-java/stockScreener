import json
stocks=[{"ticker":"ICICIBANK.NS","score":89},{"ticker":"HDFCBANK.NS","score":86},{"ticker":"MSFT","score":85},{"ticker":"AAPL","score":84}]
rankings=[]
for i,s in enumerate(sorted(stocks,key=lambda x:x["score"],reverse=True),start=1):
 rankings.append({"rank":i,"ticker":s["ticker"],"score":s["score"]})
with open("docs/rankings.json","w") as f: json.dump(rankings,f,indent=2)
print("Generated rankings.json")
