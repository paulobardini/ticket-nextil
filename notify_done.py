import os
import json
import re
import smtplib
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GH_TOKEN    = os.environ['GH_TOKEN']
GMAIL_USER  = os.environ['GMAIL_USER']
GMAIL_PASS  = os.environ['GMAIL_PASS']
SENT_FILE   = 'sent_emails.txt'
ORG         = 'appnextil'
PROJECT_NUM = 1
STATUS_DONE = 'Done'


def gql(query):
    data = json.dumps({'query': query}).encode()
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=data,
        headers={
            'Authorization': f'Bearer {GH_TOKEN}',
            'Content-Type': 'application/json',
        }
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def get_done_items():
    result = gql(f"""
        query {{
            organization(login: "{ORG}") {{
                projectV2(number: {PROJECT_NUM}) {{
                    items(first: 100) {{
                        nodes {{
                            id
                            content {{
                                ... on DraftIssue {{ title body }}
                            }}
                            fieldValues(first: 15) {{
                                nodes {{
                                    ... on ProjectV2ItemFieldSingleSelectValue {{
                                        name
                                        field {{ ... on ProjectV2SingleSelectField {{ name }} }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
    """)

    nodes = result['data']['organization']['projectV2']['items']['nodes']
    done = []
    for item in nodes:
        if not item.get('content'):
            continue
        for fv in item['fieldValues']['nodes']:
            if fv.get('name') == STATUS_DONE and fv.get('field', {}).get('name') == 'Status':
                done.append(item)
                break
    return done


def parse_field(body, emoji_label):
    match = re.search(rf'\*\*{re.escape(emoji_label)}\*\*\s*([^\n\r]+)', body)
    return match.group(1).strip() if match else None


def send_email(to_email, name, title):
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                max-width:600px;margin:0 auto;padding:32px 16px;background:#f1f5f9;">
      <div style="background:#fff;border-radius:12px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.07);">

        <div style="background:#0f172a;padding:18px 28px;">
          <img src="https://nextil.com.br/_next/static/media/logo-login.e53ac927.svg"
               height="26" alt="Nextil">
        </div>

        <div style="padding:32px 28px;">
          <h2 style="margin:0 0 8px;color:#0f172a;font-size:20px;">
            Seu ticket foi resolvido ✅
          </h2>
          <p style="margin:0 0 24px;color:#64748b;font-size:14px;line-height:1.6;">
            Olá, <strong>{name}</strong>! Seu ticket foi marcado como concluído pelo time da Nextil.
          </p>

          <div style="background:#f1f5f9;border-radius:8px;padding:16px 20px;margin-bottom:24px;">
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;
                        letter-spacing:.08em;color:#94a3b8;margin-bottom:6px;">
              Ticket resolvido
            </div>
            <div style="font-size:15px;font-weight:600;color:#0f172a;">{title}</div>
          </div>

          <p style="margin:0;color:#64748b;font-size:13px;line-height:1.6;">
            Se tiver dúvidas ou o problema persistir, abra um novo ticket em nossa central.
          </p>
        </div>

        <div style="padding:14px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;
                    text-align:center;">
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            Nextil · Central de Tickets
          </p>
        </div>
      </div>
    </div>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'✅ Ticket resolvido: {title}'
    msg['From']    = f'Nextil Tickets <{GMAIL_USER}>'
    msg['To']      = to_email
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        print(f'  ✓ Email enviado para {to_email}')
        return True
    except Exception as e:
        print(f'  ✗ Erro ao enviar para {to_email}: {e}')
        return False


def main():
    sent_ids = set()
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE) as f:
            sent_ids = {line.strip() for line in f if line.strip()}

    print(f'IDs já notificados: {len(sent_ids)}')

    done_items = get_done_items()
    print(f'Itens em Done: {len(done_items)}')

    new_ids = []
    for item in done_items:
        item_id = item['id']
        if item_id in sent_ids:
            continue

        content = item.get('content', {})
        title   = content.get('title', 'Sem título')
        body    = content.get('body', '')

        email = parse_field(body, '📧 Email:')
        name  = parse_field(body, '👤 Solicitante:') or 'Usuário'

        print(f'\nProcessando: {title}')
        if not email:
            print('  ⚠ E-mail não encontrado no corpo — pulando notificação.')
        else:
            send_email(email, name, title)

        new_ids.append(item_id)

    if new_ids:
        with open(SENT_FILE, 'a') as f:
            for i in new_ids:
                f.write(i + '\n')
        print(f'\nRegistrados {len(new_ids)} novos IDs em {SENT_FILE}')


if __name__ == '__main__':
    main()
