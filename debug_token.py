env = open('backend/.env', encoding='utf-8').read()
for line in env.split('\n'):
    if line.startswith('META_ACCESS_TOKEN='):
        t = line.split('=', 1)[1].strip()
        print('Length:', len(t))
        print('First 20 chars:', t[:20])
        print('Last 20 chars:', t[-20:])
        print('Has spaces:', ' ' in t)
        print('Has newlines:', '\n' in t or '\r' in t)
