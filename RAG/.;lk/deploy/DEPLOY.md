# Deploying QABuddy.ai to a DigitalOcean droplet (or any Docker-capable VPS)

This gets the app running 24x7 behind Docker Compose. It does **not** cover
provisioning the droplet itself — create a droplet (4GB+ RAM recommended; bge-m3
+ bge-reranker together need ~3GB resident once loaded) and SSH in first.

## 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # log out/in after this
```

## 2. Copy the app

```bash
sudo mkdir -p /opt/qabuddy && sudo chown $USER /opt/qabuddy
# from your machine:
rsync -avz --exclude .venv --exclude __pycache__ --exclude qdrant_data \
  ./QABuddy.ai/ your-user@your-droplet:/opt/qabuddy/
```

## 3. Configure environment

```bash
cd /opt/qabuddy
cp .env.example .env
nano .env   # set GROQ_API_KEY (or OPENROUTER_API_KEY)
```

## 4. Place Phase 1 data

Populate `data_sources/*` per each folder's README (clone the Selenium/Playwright
repos, drop the test-case export, PDFs, transcripts, Jenkins logs). This can also
be done later through the **Sources** tab once the app is running.

## 5. Start it

```bash
docker compose up -d --build
docker compose logs -f app   # watch first-run model downloads (~3GB, one-time)
```

Visit `http://<droplet-ip>:8060`.

## 6. Run 24x7 across reboots

```bash
sudo cp deploy/qabuddy.service /etc/systemd/system/qabuddy.service
sudo systemctl daemon-reload
sudo systemctl enable --now qabuddy.service
```

## 7. Secure it before exposing to the internet

The app itself has **no authentication** — fine for a private VPN/tailnet, not
fine on a bare public IP for an internal company tool. Put nginx in front with
basic auth and (ideally) TLS:

```bash
sudo apt install -y nginx apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd qa-team   # prompts for a shared password
```

`/etc/nginx/sites-available/qabuddy`:

```nginx
server {
    listen 80;
    server_name qabuddy.yourcompany.internal;

    auth_basic "QABuddy.ai";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8060;
        proxy_set_header Host $host;
        proxy_set_header X-Accel-Buffering no;  # required: chat/ingest use SSE streaming
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/qabuddy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Then close the droplet's firewall to port 8060/6333 from the outside (`ufw deny
8060`, `ufw deny 6333`) so traffic only reaches the app through nginx on 80/443.
Add `certbot --nginx` for TLS once you have a real domain pointed at the droplet.

## Notes

- `gunicorn_conf.py` intentionally runs **one worker process** (multiple
  threads) — bge-m3/bge-reranker are loaded once per process and never
  unloaded, so multiple worker processes would multiply memory use for no
  retrieval-quality benefit.
- Qdrant's data lives in the `qdrant_data` named volume; back it up (`docker
  run --rm -v qabuddy_qdrant_data:/data -v $PWD:/backup alpine tar czf
  /backup/qdrant_backup.tgz /data`) before any risky change.
- To re-ingest a source after updating its files, just click **Ingest** again
  in the Sources tab — it replaces that source's old chunks (see
  `core/vectorstore.delete_by_source_name`), it doesn't duplicate them.
