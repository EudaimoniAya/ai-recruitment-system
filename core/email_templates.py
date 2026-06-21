"""邮件正文模板"""

from settings import settings


def _format_expire_duration(seconds: int) -> str:
    """将秒数格式化为可读的有效期描述"""
    days, remainder = divmod(seconds, 86400)
    hours, _ = divmod(remainder, 3600)
    if days > 0 and hours > 0:
        return f"{days} 天 {hours} 小时"
    if days > 0:
        return f"{days} 天"
    if hours > 0:
        return f"{hours} 小时"
    return f"{max(seconds // 60, 1)} 分钟"


def render_invite_email(
    email: str,
    invite_code: str,
    department_name: str,
) -> tuple[str, str, str]:
    """
    生成邀请注册邮件内容。

    Returns:
        (subject, html_body, plain_body)
    """
    expire_text = _format_expire_duration(settings.invite_code_expire)
    subject = f"【AI 招聘系统】{department_name} 注册邀请"

    plain_body = f"""您好，

您已被邀请加入 AI 智能招聘系统，所属部门：{department_name}。

请使用以下验证码完成账号注册：
{invite_code}

注册邮箱：{email}
验证码有效期：{expire_text}

如非本人操作，请忽略此邮件。

—— AI 智能招聘系统
"""

    html_body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>注册邀请</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f5f7fa;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(15,23,42,0.08);">
          <tr>
            <td style="padding:28px 32px;background:linear-gradient(135deg,#2563eb 0%,#1d4ed8 100%);color:#ffffff;">
              <div style="font-size:20px;font-weight:700;line-height:1.4;">AI 智能招聘系统</div>
              <div style="margin-top:8px;font-size:14px;opacity:0.92;">账号注册邀请</div>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;color:#334155;font-size:15px;line-height:1.8;">
              <p style="margin:0 0 16px;">您好，</p>
              <p style="margin:0 0 16px;">
                您已被邀请加入 <strong style="color:#1e293b;">{department_name}</strong>，
                请使用下方验证码完成账号注册。
              </p>
              <div style="margin:24px 0;padding:20px;background-color:#f8fafc;border:1px dashed #cbd5e1;border-radius:10px;text-align:center;">
                <div style="font-size:13px;color:#64748b;margin-bottom:8px;">您的验证码</div>
                <div style="font-size:32px;font-weight:700;letter-spacing:6px;color:#2563eb;">{invite_code}</div>
              </div>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 20px;font-size:14px;color:#475569;">
                <tr>
                  <td style="padding:6px 0;width:96px;color:#64748b;">注册邮箱</td>
                  <td style="padding:6px 0;">{email}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#64748b;">所属部门</td>
                  <td style="padding:6px 0;">{department_name}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#64748b;">有效期</td>
                  <td style="padding:6px 0;">{expire_text}</td>
                </tr>
              </table>
              <p style="margin:0;font-size:13px;color:#94a3b8;">
                如非本人操作，请忽略此邮件，无需回复。
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    return subject, html_body, plain_body
