# 🌐 Deploying BlockVerify to the Live Internet

BlockVerify consists of two parts:
1. **Frontend**: Static HTML/CSS/JS files (`frontend/`)
2. **Backend**: Python Flask API (`backend/`)
3. **Database**: Local JSON files (`backend/data/*.json`)

Because your database uses local JSON files, **you cannot use standard serverless or free-tier cloud platforms** (like Heroku or Vercel for the backend) easily because they reset their filesystems every time they sleep, wiping your `backend/data/` folder.

Here are the two best ways to deploy this project depending on your budget and needs for the final evaluation.

---

## Method 1: The "Production" Way — DigitalOcean Droplet / AWS EC2 (Highly Recommended)
*Cost: ~$6/month (Free if you use GitHub Student Developer Pack credits)*

This is the standard engineering approach. You rent a small Linux server, copy your files, and run the backend continuously. Your JSON files will be completely safe.

### Step 1: Prepare the Frontend for Production
Currently, your frontend is hardcoded to talk to `localhost:5000`. You need to change this to your future live server URL.
1. Open `frontend/index.html`.
2. Find the API definition (around line 1430): `const API = 'http://localhost:5000/api';`
3. Change it to your future domain or server IP: `const API = 'http://your-server-ip-or-domain/api';` (Note: for now, leave it if you don't have the IP yet, but remember this step).

### Step 2: Set up the Server
1. Go to [DigitalOcean](https://www.digitalocean.com/) (or AWS/Linode) and create a basic **Ubuntu 24.04** Droplet. (The $4-$6/mo basic droplet is perfectly fine).
2. SSH into your new server from your terminal: 
   `ssh root@your_server_ip`

### Step 3: Install Dependencies
Run these commands on the server to install Nginx and Python:
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx git -y
```

### Step 4: Clone Your Code
```bash
git clone https://github.com/innovation-space/course-project-submission-razor_hats.git
cd course-project-submission-razor_hats/blockverify
```

### Step 5: Setup the Python Backend
Create a virtual environment and install your Python libraries:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

To keep your Flask app running permanently, we use **Gunicorn** instead of `python3 app.py`:
```bash
gunicorn --bind 0.0.0.0:5000 app:app --daemon
```
*(The `--daemon` flag runs it in the background forever).*

### Step 6: Serve the Frontend & API via Nginx
We use Nginx to serve your `frontend/index.html` on port 80 (standard HTTP) and route API requests to your Flask backend.

1. Open the Nginx config:
   `sudo nano /etc/nginx/sites-available/default`
2. Replace all the contents with this block:

```nginx
server {
    listen 80;
    server_name _; # Or your domain name or IP

    # Serve the frontend static files
    location / {
        root /root/course-project-submission-razor_hats/blockverify/frontend;
        index index.html;
    }

    # Route /api/ requests to your Flask backend
    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # VERY IMPORTANT for CORS on live servers
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
    }
}
```

3. Save (Ctrl+O, Enter, Ctrl+X) and restart Nginx:
   `sudo systemctl restart nginx`

**✅ You're live!** You can now type your DigitalOcean Droplet's IP address into a browser anywhere in the world and see BlockVerify.

---

## Method 2: The "Split" Way — Render.com + Netlify 
*Cost: Free tier available (Render free tier sleeps after 15mins of inactivity, but it's okay for a demo)*

If you don't want to manage a Linux server, you can host the Frontend and Backend separately.

**⚠️ WARNING:** Because Render.com's free tier has an "ephemeral" (temporary) disk, **your JSON database will be wiped every time the server goes to sleep or restarts.** To prevent this, you would need to upgrade to Render's $7/mo plan and attach a $1/mo "Persistent Disk" to the `backend/data` folder.

### Step 1: Deploy Backend to Render.com
1. Create an account on [Render.com](https://render.com/).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository `course-project-submission-razor_hats`.
4. Configure the settings:
   - **Root Directory**: `blockverify/backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && pip install gunicorn`
   - **Start Command**: `gunicorn app:app`
5. Click **Deploy**. Render will give you a URL like `https://blockverify-api.onrender.com`.

### Step 2: Update the Frontend
1. On your local machine, open `frontend/index.html`.
2. Change the `const API` variable to your new Render URL:
   `const API = 'https://blockverify-api.onrender.com/api';`
3. Commit and push this change to GitHub.

### Step 3: Deploy Frontend to Netlify or Vercel
1. Go to [Netlify](https://www.netlify.com/) or [Vercel](https://vercel.com/) and create a free account.
2. Click **Add New Site** -> **Import an existing project**.
3. Connect your GitHub repository.
4. Configure the settings:
   - **Base/Root Directory**: `blockverify/frontend`
   - **Build Command**: *(Leave empty)*
   - **Publish directory**: `blockverify/frontend` (or just leave empty).
5. Click **Deploy**.

**✅ You're live!** Your frontend is now live on a global CDN and talks to your Render backend.

---

### Security Note Before Exposing to the Internet
When you deploy, anyone holding the URL can access your API. Since you are using a single `Server Wallet` that funds Blockchain transactions, someone could spam your `/api/register` endpoint to drain your Testnet ALGO.
- Keep the `rate_limiter` we implemented active.
- Do not make the URL public before your presentation.
