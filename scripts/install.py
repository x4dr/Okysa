#!/usr/bin/env python3
import os
import re
import secrets
import subprocess
from pathlib import Path


def get_input(prompt, default=None):
    if default:
        res = input(f"{prompt} [{default}]: ").strip()
        return res if res else default
    return input(f"{prompt}: ").strip()


def detect_domains():
    domains = []
    sites_enabled = Path("/etc/nginx/sites-enabled")
    if not sites_enabled.exists():
        return domains

    for site in sites_enabled.iterdir():
        try:
            content = site.read_text()
            matches = re.findall(r"server_name\s+([^;]+);", content)
            for match in matches:
                for domain in match.split():
                    if domain and not domain.startswith("_"):
                        domains.append(domain)
        except Exception:
            continue
    return sorted(list(set(domains)))


def register_webhook(domain, secret):
    print("\n--- GitHub Webhook Registration ---")
    use_gh = get_input("Use 'gh' CLI to register webhook?", "y")
    if use_gh.lower() != "y":
        return False

    # Check if gh is installed
    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        print("Error: 'gh' CLI not found. Please install it first.")
        return False

    # Check GH auth status
    auth_check = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if auth_check.returncode != 0:
        print("GitHub CLI is not authenticated.")
        do_login = get_input("Run 'gh auth login' now?", "y")
        if do_login.lower() == "y":
            try:
                # Use standard run to allow interactive login
                subprocess.run(["gh", "auth", "login"], check=True)
            except subprocess.CalledProcessError:
                print("Login failed. Skipping webhook registration.")
                return False
        else:
            print("Skipping webhook registration.")
            return False

    webhook_url = f"https://{domain}/webhook"
    try:
        subprocess.run(
            [
                "gh",
                "repo",
                "webhook",
                "create",
                "--url",
                webhook_url,
                "--secret",
                secret,
                "--events",
                "workflow_run",
                "--content-type",
                "json",
            ],
            check=True,
        )
        print(f"Successfully registered webhook: {webhook_url}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to register webhook: {e}")
        return False


def main():
    # 1. Detect Paths
    script_path = Path(__file__).resolve()
    okysa_root = script_path.parent.parent
    gamepack_root = okysa_root.parent / "GamePack"
    uv_path = subprocess.getoutput("which uv") or "uv"

    print("--- Path Detection ---")
    print(f"Okysa Root:    {okysa_root}")
    if gamepack_root.exists():
        print(f"GamePack Root: {gamepack_root}")
    else:
        print(f"WARNING: GamePack not found at {gamepack_root}")
        gamepack_root_str = get_input(
            "Enter absolute path to GamePack", str(gamepack_root)
        )
        gamepack_root = Path(gamepack_root_str)

    # 2. Gather Configuration
    print("\n--- Configuration ---")
    user = get_input("System user to run the bot", os.getlogin())

    detected_domains = detect_domains()
    default_domain = "nossinet.cc"
    if detected_domains:
        print("Detected domains from Nginx:")
        for i, d in enumerate(detected_domains):
            print(f"  {i + 1}. {d}")
        choice = get_input(
            f"Choose domain (1-{len(detected_domains)}) or enter new", "1"
        )
        if choice.isdigit() and 1 <= int(choice) <= len(detected_domains):
            domain = detected_domains[int(choice) - 1]
        else:
            domain = choice
    else:
        domain = get_input("Domain for Nginx", default_domain)

    webhook_secret = secrets.token_urlsafe(32)

    # 3. Update scripts with absolute paths
    deploy_sh_path = okysa_root / "scripts" / "deploy.sh"
    webhook_py_path = okysa_root / "scripts" / "webhook_listener.py"

    deploy_content = f"""#!/bin/bash
set -e
PROJECT_ROOT="{okysa_root}"
GAMEPACK_ROOT="{gamepack_root}"

echo "[$(date)] Starting redeployment..."
cd "$GAMEPACK_ROOT" && git pull
cd "$PROJECT_ROOT" && git pull

# uv sync ensures the environment is ready
{uv_path} sync --all-extras

sudo systemctl restart okysa.service
echo "[$(date)] Deployment successful!"
"""

    with open(deploy_sh_path, "w") as f:
        f.write(deploy_content)
    os.chmod(deploy_sh_path, 0o755)

    with open(webhook_py_path, "r") as f:
        lines = f.readlines()

    with open(webhook_py_path, "w") as f:
        for line in lines:
            if line.startswith("DEPLOY_SCRIPT ="):
                f.write(f'DEPLOY_SCRIPT = "{deploy_sh_path}"\n')
            else:
                f.write(line)

    # 4. Generate Systemd Units
    bot_service = f"""[Unit]
Description=Okysa Discord Bot
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={okysa_root}
# Using uv run ensures the venv is automatically updated/checked
ExecStart={uv_path} run Okysa.py
Restart=always

[Install]
WantedBy=multi-user.target
"""

    webhook_service = f"""[Unit]
Description=Okysa Webhook Listener
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={okysa_root}
Environment="GITHUB_WEBHOOK_SECRET={webhook_secret}"
ExecStart=/usr/bin/python3 {webhook_py_path}
Restart=always

[Install]
WantedBy=multi-user.target
"""

    # 5. Generate Nginx Config
    nginx_conf = f"""server {{
    listen 80;
    server_name {domain};

    location /webhook {{
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    # ... rest of your config ...
}}
"""

    print("\n--- Systemd: Bot Service (/etc/systemd/system/okysa.service) ---")
    print(bot_service)

    print(
        "--- Systemd: Webhook Service (/etc/systemd/system/okysa-webhook.service) ---"
    )
    print(webhook_service)

    print(f"--- Nginx: Config (/etc/nginx/sites-available/{domain}) ---")
    print(nginx_conf)

    print("\n--- Proposed Actions ---")
    print("1. Write /etc/systemd/system/okysa.service")
    print("2. Write /etc/systemd/system/okysa-webhook.service")
    print(f"3. Write /etc/nginx/sites-available/{domain}")
    print("4. Add sudoers entry for systemctl restart")

    do_install = get_input("Perform these actions? (requires sudo)", "n")
    if do_install.lower() == "y":

        def sudo_write(content, path):
            subprocess.run(
                ["sudo", "tee", str(path)],
                input=content.encode(),
                stdout=subprocess.DEVNULL,
            )

        sudo_write(bot_service, "/etc/systemd/system/okysa.service")
        sudo_write(webhook_service, "/etc/systemd/system/okysa-webhook.service")
        sudo_write(nginx_conf, f"/etc/nginx/sites-available/{domain}")

        sudoers_line = (
            f"{user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart okysa.service\n"
        )
        sudo_write(sudoers_line, "/etc/sudoers.d/okysa-deploy")

        link_nginx = get_input(f"Link /etc/nginx/sites-enabled/{domain}? (y/n)", "y")
        if link_nginx.lower() == "y":
            subprocess.run(
                [
                    "sudo",
                    "ln",
                    "-sf",
                    f"/etc/nginx/sites-available/{domain}",
                    f"/etc/nginx/sites-enabled/{domain}",
                ]
            )
            print("Linked nginx config.")

        subprocess.run(["sudo", "systemctl", "daemon-reload"])

        start_now = get_input("Enable and start services now? (y/n)", "y")
        if start_now.lower() == "y":
            subprocess.run(
                ["sudo", "systemctl", "enable", "--now", "okysa-webhook", "okysa"]
            )
            print("Services enabled and started.")

        register_webhook(domain, webhook_secret)

        print("\nInstallation complete.")
        print(f"Your GitHub Webhook Secret is: {webhook_secret}")
    else:
        print(
            "\nInstallation aborted. You can manually use the configurations printed above."
        )


if __name__ == "__main__":
    main()
