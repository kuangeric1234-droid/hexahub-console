import urllib.request, json

env = open('backend/.env').read()
token = next(l.split('=',1)[1].strip() for l in env.split('\n') if l.startswith('META_ACCESS_TOKEN='))

params = f"id,username"
url = "https://graph.facebook.com/v19.0/17841447176714314?fields=" + params + "&access_token=" + token

try:
    r = urllib.request.urlopen(url)
    print(json.loads(r.read()))
except urllib.error.HTTPError as e:
    print(json.loads(e.read()))
