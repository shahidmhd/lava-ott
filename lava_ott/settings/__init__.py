import os

f_path = os.path.join(os.path.dirname(__file__), '.dj-env')
if not os.path.exists(f_path):
    raise SystemExit(".dj-env is not present. Please create one.")
fp = open(f_path)
env = fp.read().strip()
print('env: ', env)

if env == 'development':
    from .development import *
if env == 'testing':
    from .testing import *
if env == 'production':
    from .production import *
