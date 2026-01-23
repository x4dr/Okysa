#!/usr/bin/env python3
import argparse
import getpass
import json
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


def get_current_user():
    try:
        return os.getlogin()
    except OSError:
        return getpass.getuser()


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


def get_repo_nwo():
    try:
        res = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def register_webhook(domain, secret):
    print("\n--- GitHub Webhook Registration ---")
    use_gh = get_input("Use 'gh' CLI to register/update webhook?", "y")
    if use_gh.lower() != "y":
        return False

    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        print("Error: 'gh' CLI not found.")
        return False

    # Check GH auth status
    auth_check = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if auth_check.returncode != 0:
        print("GitHub CLI is not authenticated.")
        if get_input("Run 'gh auth login' now?", "y").lower() == "y":
            try:
                subprocess.run(["gh", "auth", "login"], check=True)
            except subprocess.CalledProcessError:
                return False
        else:
            return False

    nwo = get_repo_nwo()
    if not nwo:
        print("Could not determine repository name.")
        return False

    webhook_url = f"https://{domain}/webhook"

    # Check for existing webhook
    try:
        hooks_json = subprocess.run(
            ["gh", "api", f"repos/{nwo}/hooks"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        hooks = json.loads(hooks_json)
        existing_hook = next(
            (h for h in hooks if h.get("config", {}).get("url") == webhook_url), None
        )

        if existing_hook:
            print(f"Found existing webhook (ID: {existing_hook['id']}). Updating...")
            cmd = [
                "gh",
                "api",
                f"repos/{nwo}/hooks/{existing_hook['id']}",
                "--method",
                "PATCH",
                "-f",
                "active=true",
                "-f",
                "events[]=workflow_run",
                "-f",
                f"config[url]={webhook_url}",
                "-f",
                "config[content_type]=json",
                "-f",
                f"config[secret]={secret}",
            ]
        else:
            print("Creating new webhook...")
            cmd = [
                "gh",
                "api",
                f"repos/{nwo}/hooks",
                "--method",
                "POST",
                "-f",
                "name=web",
                "-f",
                "active=true",
                "-f",
                "events[]=workflow_run",
                "-f",
                f"config[url]={webhook_url}",
                "-f",
                "config[content_type]=json",
                "-f",
                f"config[secret]={secret}",
            ]

        subprocess.run(cmd, check=True)
        print(f"Successfully registered/updated webhook: {webhook_url}")
        return True
    except Exception as e:
        print(f"Failed to manage webhook: {e}")
        return False


def uninstall(okysa_root):
    print("\n--- Uninstalling Okysa Deployment ---")

    # Stop and disable services
    services = ["okysa.service", "okysa-webhook.service"]
    for svc in services:
        print(f"Stopping and disabling {svc}...")
        subprocess.run(["sudo", "systemctl", "stop", svc], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "systemctl", "disable", svc], stderr=subprocess.DEVNULL)
        subprocess.run(
            ["sudo", "rm", f"/etc/systemd/system/{svc}"], stderr=subprocess.DEVNULL
        )

    # Nginx
    sites_available = Path("/etc/nginx/sites-available")
    if sites_available.exists():
        for site in sites_available.iterdir():
            try:
                content = site.read_text()
                if str(okysa_root) in content:
                    print(f"Removing Nginx config: {site.name}")
                    subprocess.run(
                        ["sudo", "rm", f"/etc/nginx/sites-enabled/{site.name}"],
                        stderr=subprocess.DEVNULL,
                    )
                    subprocess.run(["sudo", "rm", str(site)], stderr=subprocess.DEVNULL)
            except:
                continue

    # Sudoers
    print("Removing sudoers entry...")
    subprocess.run(
        ["sudo", "rm", "/etc/sudoers.d/okysa-deploy"], stderr=subprocess.DEVNULL
    )

    subprocess.run(["sudo", "systemctl", "daemon-reload"])
    print("\nUninstallation complete.")


def main():
    parser = argparse.ArgumentParser(description="Okysa Deployment Installer")
    parser.add_argument(
        "--uninstall", action="store_true", help="Uninstall the deployment"
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    okysa_root = script_path.parent.parent

    if args.uninstall:
        uninstall(okysa_root)
        return

    gamepack_root = okysa_root.parent / "GamePack"
    uv_path = subprocess.getoutput("which uv") or "uv"

    print("--- Path Detection ---")
    print(f"Okysa Root:    {okysa_root}")
    if gamepack_root.exists():
        print(f"GamePack Root: {gamepack_root}")
    else:
        print(f"WARNING: GamePack not found at {gamepack_root}")
        gamepack_root = Path(
            get_input("Enter absolute path to GamePack", str(gamepack_root))
        )

    # 2. Gather Configuration
    print("\n--- Configuration ---")
    user = get_input("System user to run the bot", get_current_user())

    detected_domains = detect_domains()
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
        domain = get_input("Domain for Nginx", "nossinet.cc")

    webhook_secret = secrets.token_urlsafe(32)

    # 3. Update scripts
    deploy_sh_path = okysa_root / "scripts" / "deploy.sh"
    webhook_py_path = okysa_root / "scripts" / "webhook_listener.py"

    deploy_content = f"""#!/bin/bash
set -e
PROJECT_ROOT="{okysa_root}"
GAMEPACK_ROOT="{gamepack_root}"

echo "[$(date)] Starting redeployment..."
cd "$GAMEPACK_ROOT" && git pull
cd "$PROJECT_ROOT" && git pull
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
}}
"""

    print("\n--- Proposed Actions ---")
    print("1. Write /etc/systemd/system/okysa.service")
    print("2. Write /etc/systemd/system/okysa-webhook.service")
    print(f"3. Write /etc/nginx/sites-available/{domain}")
    print("4. Add sudoers entry for systemctl restart")

    if get_input("Perform these actions? (requires sudo)", "n").lower() == "y":

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

        if (
            get_input(f"Link /etc/nginx/sites-enabled/{domain}? (y/n)", "y").lower()
            == "y"
        ):
            subprocess.run(
                [
                    "sudo",
                    "ln",
                    "-sf",
                    f"/etc/nginx/sites-available/{domain}",
                    f"/etc/nginx/sites-enabled/{domain}",
                ]
            )

        subprocess.run(["sudo", "systemctl", "daemon-reload"])
        if get_input("Enable and start services now? (y/n)", "y").lower() == "y":
            subprocess.run(
                ["sudo", "systemctl", "enable", "--now", "okysa-webhook", "okysa"]
            )

        register_webhook(domain, webhook_secret)
        print(f"\nInstallation complete. Secret: {webhook_secret}")
    else:
        print("\nInstallation aborted.")


if __name__ == "__main__":
    main()
