"""Verify the user's actual Railway DATABASE_URL is accepted."""
import os
import re

user_url = 'postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:%5BAChawhan%401234%5D@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require'
print(f'User URL: {user_url}')
print()

placeholders = re.findall(r'<[A-Z_]+>', user_url)
print(f'Placeholders found: {placeholders or "NONE"}')
print()

os.environ['DATABASE_URL'] = user_url
os.environ['APP_SECRET_KEY'] = 'test'
os.environ['WORKER_ENABLED'] = 'false'
os.environ['DB_STARTUP_TIMEOUT'] = '5'

try:
    from app.main import app
    print(f'OK: app loaded with user actual URL ({len(app.routes)} routes)')
except Exception as e:
    err = str(e)
    if 'unresolved placeholder' in err:
        print('FAIL: validator rejected the URL')
        ph = re.search(r"'<[^>]+>'", err)
        if ph:
            print(f'  rejected placeholder: {ph.group(0)}')
        else:
            print(f'  full error: {err[:200]}')
    else:
        print(f'OTHER ERROR: {err[:300]}')
