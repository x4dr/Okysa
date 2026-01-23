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
    domain_map = {}
    sites_enabled = Path("/etc/nginx/sites-enabled")
    if not sites_enabled.exists():
        return domain_map

    for site in sites_enabled.iterdir():
        if ".bak." in site.name:
            continue
        try:
            content = site.read_text()
            # Match lines that start with server_name (ignoring comments)
            matches = re.findall(r"^\s*server_name\s+([^;]+);", content, re.MULTILINE)
            for match in matches:
                for domain in match.split():
                    if domain and not domain.startswith("_"):
                        domain_map[domain] = site
        except Exception:
            continue
    return domain_map


def cleanup_legacy_backups():
    print("Checking for legacy backup files in Nginx directories...")
    paths = [Path("/etc/nginx/sites-enabled"), Path("/etc/nginx/sites-available")]
    for p in paths:
        if p.exists():
            for f in p.iterdir():
                if ".bak." in f.name:
                    print(f"Removing legacy backup: {f}")
                    subprocess.run(["sudo", "rm", str(f)], check=True)


def inject_nginx_config(filepath, domain, block):
    content = filepath.read_text()
    if block.strip() in content:
        print(f"Webhook block already exists in {filepath.name}. Skipping injection.")
        return True

    # Backup
    backup_dir = filepath.parent.parent / "backups"
    if not backup_dir.exists():
        subprocess.run(["sudo", "mkdir", "-p", str(backup_dir)], check=True)

    backup = backup_dir / f"{filepath.name}.bak.{secrets.token_hex(4)}"
    subprocess.run(["sudo", "cp", str(filepath), str(backup)], check=True)
    print(f"Created Nginx backup: {backup}")

    # Injection logic
    # Find the server block for the domain
    # We look for server_name domain; and then backtrack to find the closest server { before it
    # But a simpler way is to find the server { that contains server_name domain;
    # and then find the last } of that block.

    lines = content.splitlines()
    in_server_block = False
    brace_count = 0

    # This is a basic parser that looks for the server block containing the domain
    for i, line in enumerate(lines):
        if "server {" in line:
            in_server_block = True
            brace_count = 1
            continue

        if in_server_block:
            brace_count += line.count("{")
            brace_count -= line.count("}")

            if domain in line and "server_name" in line:
                # Found the right block. Now find where it ends.
                # Continue until brace_count is 0
                for j in range(i + 1, len(lines)):
                    brace_count += lines[j].count("{")
                    brace_count -= lines[j].count("}")
                    if brace_count == 0:
                        # Insert before this line
                        new_lines = lines[:j] + [block] + lines[j:]
                        new_content = "\n".join(new_lines)

                        # Write and test
                        try:
                            subprocess.run(
                                ["sudo", "tee", str(filepath)],
                                input=new_content.encode(),
                                stdout=subprocess.DEVNULL,
                                check=True,
                            )
                            print("Injected webhook block into existing Nginx config.")
                            if subprocess.run(["sudo", "nginx", "-t"]).returncode == 0:
                                return True
                            else:
                                print("Nginx test failed! Rolling back...")
                                subprocess.run(
                                    ["sudo", "cp", str(backup), str(filepath)],
                                    check=True,
                                )
                                return False
                        except Exception as e:
                            print(f"Error during injection: {e}")
                            subprocess.run(
                                ["sudo", "cp", str(backup), str(filepath)], check=True
                            )
                            return False

            if brace_count == 0:
                in_server_block = False

    print(f"Could not find a suitable server block for {domain} in {filepath.name}.")
    return False


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


def register_webhook(domain, existing_secret):
    print("\n--- GitHub Webhook Registration ---")
    use_gh = get_input("Use 'gh' CLI to register/update webhook?", "y")
    if use_gh.lower() != "y":
        return None

    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        print("Error: 'gh' CLI not found.")
        return None

    # Check GH auth status
    auth_check = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if auth_check.returncode != 0:
        print("GitHub CLI is not authenticated.")
        if get_input("Run 'gh auth login' now?", "y").lower() == "y":
            try:
                subprocess.run(["gh", "auth", "login"], check=True)
            except subprocess.CalledProcessError:
                return None
        else:
            return None

    nwo = get_repo_nwo()
    if not nwo:
        print("Could not determine repository name.")
        return None

    webhook_url = f"https://{domain}/webhook"

    # Generate new secret if needed
    secret = existing_secret or secrets.token_urlsafe(32)

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

        hook_data = {
            "active": True,
            "events": ["workflow_run"],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
            },
        }

        if existing_hook:
            print(f"Found existing webhook (ID: {existing_hook['id']}). Updating...")
            endpoint = f"repos/{nwo}/hooks/{existing_hook['id']}"
            method = "PATCH"
        else:
            print("Creating new webhook...")
            hook_data["name"] = "web"
            endpoint = f"repos/{nwo}/hooks"
            method = "POST"

        subprocess.run(
            ["gh", "api", endpoint, "--method", method, "--input", "-"],
            input=json.dumps(hook_data),
            text=True,
            check=True,
        )
        print(f"Successfully registered/updated webhook: {webhook_url}")
        return secret
    except Exception as e:
        print(f"Failed to manage webhook: {e}")
        return None


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
                if "# Managed by Okysa Installer" in content:
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


def load_env(env_path):
    env_vars = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars


def save_env(env_path, env_vars):
    with open(env_path, "w") as f:
        for k, v in sorted(env_vars.items()):
            f.write(f'{k}="{v}"\n')


def main():
    parser = argparse.ArgumentParser(description="Okysa Deployment Installer")
    parser.add_argument(
        "--uninstall", action="store_true", help="Uninstall the deployment"
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    okysa_root = script_path.parent.parent
    env_path = okysa_root / ".env"
    home_dir = str(Path.home())

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

    env_vars = load_env(env_path)

    def to_generic(p):
        return str(p).replace(home_dir, "~")

    # Required Env Vars
    env_vars["NOSSI"] = get_input(
        "NOSSI (domain for web services)", env_vars.get("NOSSI", "nossinet.cc")
    )
    env_vars["OLLAMA"] = get_input(
        "OLLAMA (URL for AI API)",
        env_vars.get("OLLAMA", "http://localhost:11434"),
    )
    env_vars["WIKI"] = get_input(
        "WIKI (path to wiki files)",
        env_vars.get("WIKI", to_generic(okysa_root.parent / "wiki")),
    )
    env_vars["STORAGE"] = get_input(
        "STORAGE (path to storage JSON)",
        env_vars.get("STORAGE", to_generic(okysa_root / "Golconda_storage.json")),
    )

    # Database detection and prompts
    # Look for known historical locations
    possible_dbs = [
        okysa_root / "okysa.db",
        Path.home() / "NN.db",
        okysa_root / "Golconda" / "remind.db",
    ]
    db_files = [to_generic(f) for f in possible_dbs if f.exists()]

    # Also scan for any other .db files in project
    scan_dbs = list(okysa_root.glob("*.db")) + list(
        (okysa_root / "Golconda").glob("*.db")
    )
    for f in scan_dbs:
        gf = to_generic(f)
        if gf not in db_files:
            db_files.append(gf)

    if db_files:
        print(f"\nDetected existing database files: {', '.join(db_files)}")
        if "~/NN.db" in db_files:
            print(
                "Note: ~/NN.db was detected and contains historical configs/chatlogs."
            )

    env_vars["DATABASE"] = get_input(
        "DATABASE (path to main okysa.db)",
        env_vars.get(
            "DATABASE",
            (
                to_generic(Path.home() / "NN.db")
                if (Path.home() / "NN.db").exists()
                else to_generic(okysa_root / "okysa.db")
            ),
        ),
    )
    env_vars["REMIND_DATABASE"] = get_input(
        "REMIND_DATABASE (path to remind.db)",
        env_vars.get(
            "REMIND_DATABASE", to_generic(okysa_root / "Golconda" / "remind.db")
        ),
    )

    # Storage detection
    possible_storages = [
        okysa_root / "Golconda_storage.json",
    ]
    storage_files = [to_generic(f) for f in possible_storages if f.exists()]
    if storage_files:
        print(f"\nDetected storage files: {', '.join(storage_files)}")

    env_vars["STORAGE"] = get_input(
        "STORAGE (path to storage JSON)",
        env_vars.get(
            "STORAGE",
            to_generic(okysa_root / "Golconda_storage.json"),
        ),
    )

    if "DISCORD_TOKEN" not in env_vars:
        token_path = Path.home() / "token.discord"
        default_token = ""
        if token_path.exists():
            default_token = token_path.read_text().strip()
        env_vars["DISCORD_TOKEN"] = get_input(
            "DISCORD_TOKEN", env_vars.get("DISCORD_TOKEN", default_token)
        )

    domain_map = detect_domains()
    domain = ""
    existing_config = None
    if domain_map:
        print("\nDetected domains from Nginx:")
        sorted_domains = sorted(list(domain_map.keys()))
        for i, d in enumerate(sorted_domains):
            print(f"  {i + 1}. {d} (in {domain_map[d].name})")
        choice = get_input(f"Choose domain (1-{len(sorted_domains)}) or enter new", "1")
        if choice.isdigit() and 1 <= int(choice) <= len(sorted_domains):
            domain = sorted_domains[int(choice) - 1]
            existing_config = domain_map[domain]
        else:
            domain = choice
    else:
        domain = get_input("Domain for Nginx", env_vars.get("NOSSI", "nossinet.cc"))

    # 3. Prepare scripts
    deploy_sh_path = okysa_root / "scripts" / "deploy.sh"
    webhook_py_path = okysa_root / "scripts" / "webhook_listener.py"

    # Ensure scripts are executable
    os.chmod(deploy_sh_path, 0o755)
    os.chmod(webhook_py_path, 0o755)

    # 4. Generate Systemd Units
    # Use %h for home directory to avoid hardcoding the username in the unit files
    home_dir = str(Path.home())
    okysa_root_generic = str(okysa_root).replace(home_dir, "%h")
    env_path_generic = str(env_path).replace(home_dir, "%h")
    uv_path_generic = str(uv_path).replace(home_dir, "%h")

    bot_service = f"""[Unit]
Description=Okysa Discord Bot
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={okysa_root_generic}
EnvironmentFile={env_path_generic}
ExecStart={uv_path_generic} run Okysa.py
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
WorkingDirectory={okysa_root_generic}
EnvironmentFile={env_path_generic}
ExecStart=/usr/bin/python3 {okysa_root_generic}/scripts/webhook_listener.py
Restart=always

[Install]
WantedBy=multi-user.target
"""

    # 5. Generate Nginx Config
    nginx_block = """
    location /webhook {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
"""
    nginx_conf = f"""# Managed by Okysa Installer
server {{
    listen 80;
    server_name {domain};
{nginx_block}
}}
"""

    print("\n--- Proposed Actions ---")
    print(f"1. Save configuration to {env_path}")
    print("2. Write /etc/systemd/system/okysa.service")
    print("3. Write /etc/systemd/system/okysa-webhook.service")
    if existing_config:
        print(f"4. Inject /webhook into existing config: {existing_config.name}")
    else:
        print(f"4. Write new Nginx config: /etc/nginx/sites-available/{domain}")
    print("5. Add sudoers entry for systemctl restart")

    if get_input("Perform these actions? (requires sudo)", "n").lower() == "y":
        cleanup_legacy_backups()
        save_env(env_path, env_vars)
        print(f"Configuration saved to {env_path}")

        def sudo_write(content, path):
            subprocess.run(
                ["sudo", "tee", str(path)],
                input=content.encode(),
                stdout=subprocess.DEVNULL,
            )

        sudo_write(bot_service, "/etc/systemd/system/okysa.service")
        sudo_write(webhook_service, "/etc/systemd/system/okysa-webhook.service")

        if existing_config:
            inject_nginx_config(existing_config, domain, nginx_block)
        else:
            target_path = Path(f"/etc/nginx/sites-available/{domain}")
            if target_path.exists():
                backup_dir = target_path.parent.parent / "backups"
                if not backup_dir.exists():
                    subprocess.run(["sudo", "mkdir", "-p", str(backup_dir)], check=True)

                new_backup = (
                    backup_dir / f"{target_path.name}.bak.{secrets.token_hex(4)}"
                )
                print(
                    f"Existing config found at {target_path}. Backing up to {new_backup}"
                )
                subprocess.run(
                    ["sudo", "cp", str(target_path), str(new_backup)], check=True
                )

            sudo_write(nginx_conf, str(target_path))
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

        # Reload Nginx regardless of method (inject handles its own test)
        print("Reloading Nginx...")
        subprocess.run(["sudo", "systemctl", "reload", "nginx"])

        sudoers_line = (
            f"{user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart okysa.service\n"
        )
        sudo_write(sudoers_line, "/etc/sudoers.d/okysa-deploy")

        subprocess.run(["sudo", "systemctl", "daemon-reload"])
        if get_input("Enable and start services now? (y/n)", "y").lower() == "y":
            subprocess.run(
                ["sudo", "systemctl", "enable", "--now", "okysa-webhook", "okysa"]
            )

        # Register webhook and only update secret if user said yes
        new_secret = register_webhook(domain, env_vars.get("GITHUB_WEBHOOK_SECRET"))
        if new_secret:
            env_vars["GITHUB_WEBHOOK_SECRET"] = new_secret
            save_env(env_path, env_vars)
            print(f"Updated {env_path} with the registered webhook secret.")
            print(f"Secret: {new_secret}")
        else:
            print("Webhook registration skipped or failed. Secret not updated in .env.")
            current_secret = env_vars.get("GITHUB_WEBHOOK_SECRET")
            if current_secret:
                print(f"Current secret preserved: {current_secret}")

        print("\nInstallation complete.")
    else:
        print("\nInstallation aborted. No changes made.")


if __name__ == "__main__":
    main()
