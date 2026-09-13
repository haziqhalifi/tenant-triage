import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('\"\''))


class Config:
    def __init__(self, demo=None, db=None):
        load_env()
        self.demo = os.getenv('APP_MODE', 'demo') == 'demo' if demo is None else demo
        self.db = db or str(ROOT / 'data' / ('demo.sqlite3' if self.demo else 'live.sqlite3'))
        self.openai_key = os.getenv('OPENAI_API_KEY', '')
        self.openrouter_key = os.getenv('OPENROUTER_API_KEY', '')
        self.model = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini') if self.openrouter_key else os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.resend_key = os.getenv('RESEND_API_KEY', '')
        self.sender = os.getenv('RESEND_FROM', '')
        self.manager_email = os.getenv('MANAGER_EMAIL', '')
        self.manager = 'manager-demo' if self.demo else os.getenv('MANAGER_CHAT_ID', '')
        self.tenant = 'tenant-demo' if self.demo else os.getenv('TENANT_CHAT_ID', '')
        self.tenant_name = os.getenv('TENANT_NAME', 'Aina')
        self.unit = os.getenv('UNIT_ID', 'B-12-03')
        self.property = os.getenv('PROPERTY_NAME', 'Sentul Residence')

    def validate(self):
        if not self.demo:
            required = {'OPENROUTER_API_KEY or OPENAI_API_KEY': self.openrouter_key or self.openai_key, 'TELEGRAM_BOT_TOKEN': self.telegram_token,
                        'MANAGER_CHAT_ID': self.manager,
                        'TENANT_CHAT_ID': self.tenant}
            missing = [k for k, v in required.items() if not v]
            if missing:
                raise ValueError('Live mode requires: ' + ', '.join(missing))
            email_settings = [self.resend_key, self.sender, self.manager_email]
            if any(email_settings) and not all(email_settings):
                raise ValueError('Set all Resend settings or leave RESEND_API_KEY, RESEND_FROM, and MANAGER_EMAIL empty.')
            if self.manager == self.tenant or not self.manager.isdigit() or not self.tenant.isdigit():
                raise ValueError('Use distinct positive numeric private-chat IDs for manager and tenant.')
