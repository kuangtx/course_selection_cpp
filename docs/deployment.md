# Ubuntu deployment

Follow the root README to build the extension on the server using its Python
interpreter. Keep the source repository outside the public web root. Install
runtime dependencies in a virtual environment. The example below assumes the
project is at /home/ubuntu/course_selection_cpp and its venv is .venv.

## Persistent backend process

Create /etc/systemd/system/course-selection.service:

```ini
[Unit]
Description=Course Selection API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/course_selection_cpp
ExecStart=/home/ubuntu/course_selection_cpp/.venv/bin/python3 -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Stop any manually launched Uvicorn before enabling the service to avoid a port
conflict. Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now course-selection
sudo journalctl -u course-selection -n 30 --no-pager
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/catalog
```

Changing backend code requires `sudo systemctl restart course-selection` and
resets in-memory selections. Do not use --reload or multiple workers in deployment.

## Static frontend and HTTPS

```bash
cd frontend
npm ci
npm run build
sudo mkdir -p /var/www/course1107
sudo cp -r dist/assets /var/www/course1107/
sudo cp dist/index.html /var/www/course1107/index.html
```

Install the certificate chain and private key outside the repository. Adapt the
following server block with your actual domain and certificate paths:

```nginx
server {
    listen 443 ssl;
    server_name example.com;
    ssl_certificate /etc/nginx/ssl/example.com_bundle.crt;
    ssl_certificate_key /etc/nginx/ssl/example.com.key;

    location = /course1107 { return 301 /course1107/; }
    location /course1107/ {
        root /var/www;
        try_files $uri $uri/ /course1107/index.html;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site in sites-enabled, run `sudo nginx -t`, then reload Nginx. Open
TCP 443 at the cloud firewall. Keep backend port 8000 local. Configure DNS and
certificate renewal for your actual hosting environment.

The proxy_pass intentionally has no trailing slash: it preserves `/api/`.
The compiled index.html must reference `/course1107/assets/`, not `/assets/`.
A successful HTML response alone does not prove the JS/CSS or API loaded. Check
browser Network/Console and Nginx access/error logs when troubleshooting.

Frontend updates need a new build and complete asset upload, but no backend
restart. Upload assets before index.html to avoid referencing files not uploaded
yet. Keep the previous build until the update is confirmed.

Before public multi-user use, implement authentication, admin authorization,
persistent state, request limits, and backup/restore. The current demo exposes
student switching and global state mutations without authorization.
