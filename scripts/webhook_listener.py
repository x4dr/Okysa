#!/usr/bin/env python3
import hmac
import hashlib
import json
import os
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configuration
PORT = 5000
SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")
DEPLOY_SCRIPT = "/home/maric/PycharmProjects/Okysa/scripts/deploy.sh"

if not SECRET:
    print("WARNING: GITHUB_WEBHOOK_SECRET not set. Webhook will not be secure.")


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        # 1. Verify Signature
        if SECRET:
            signature = self.headers.get("X-Hub-Signature-256")
            if not signature:
                self.send_response(401)
                self.end_headers()
                return

            expected_signature = (
                "sha256="
                + hmac.new(SECRET.encode(), post_data, hashlib.sha256).hexdigest()
            )

            if not hmac.compare_digest(signature, expected_signature):
                self.send_response(403)
                self.end_headers()
                return

        # 2. Parse Payload
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        event = self.headers.get("X-GitHub-Event")

        # 3. Handle workflow_run event
        if event == "workflow_run":
            workflow_run = payload.get("workflow_run", {})
            workflow_name = workflow_run.get("name")
            status = workflow_run.get("status")
            conclusion = workflow_run.get("conclusion")
            branch = workflow_run.get("head_branch")

            print(
                f"Received workflow_run: {workflow_name} | {branch} | {status}/{conclusion}"
            )

            # Trigger deploy only if Validation workflow succeeded on main
            if (
                workflow_name == "Validation"
                and branch == "main"
                and status == "completed"
                and conclusion == "success"
            ):
                print("Triggering deployment...")
                subprocess.Popen([DEPLOY_SCRIPT])
                self.send_response(202)  # Accepted
                self.end_headers()
                self.wfile.write(b"Deployment triggered")
                return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Event received")


def run():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, WebhookHandler)
    print(f"Starting webhook listener on port {PORT}...")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
