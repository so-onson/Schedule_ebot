**Small Telegram bot for time tracking**
---

Created for own use and for fun (just to try Telegram technologies 🥸)  
It doesn\`t use a lot of fiches, but if you\`re interested in it, you can find *ebot* by this link: [@schedule_ebot](t.me/schedule_ebot)  
Also you can try to run it on your server by following instruction below...

## Tech stack
- Python 3.10+
- [aiogram](https://docs.aiogram.dev/) (Telegram Bot Framework)
- SQLite (local database)
- APScheduler (background tasks)
- Telegram Bot API

## Some instructions

There you can find instruction to run it on **your** server   
(not auto, if you kinda lazy like me and found free server - cool, but my attempts were unsuccessful)

0. Install python or apdate and upgrade it
1. Clone repository
```bash
  git clone https://github.com/so-onson/Schedule_ebot.git
  cd Schedule_ebot
```
2. Create virtual environment (recommended)
```
  python3 -m venv <name>
  source <name>/bin/activate
```
3. Install dependencies in the project folder (also this step needed for lazy-way)
```
  pip install -r requirements.txt
``` 
4. Configure bot token
Create config.py or write string in `.env` using this command: `nano .env`
```
  TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
```
To close nano use: (smtms i forget it)
```
 CTRL + O
 ENTER
 CTRL + X
```
You can get token from: [BotFather](https://t.me/BotFather)
5. Set background running (systemd, Unit)  (for server)
You can use `screen` or `nohub` instead 
```
 sudo cp schedule.service /etc/systemd/system/
 sudo systemctl daemon-reload
 sudo systemctl start schedule.service
 sudo systemctl enable schedule.service
```
To stop: `sudo systemctl stop schedule.service`  
To start: `sudo systemctl start schedule.service`  
To restart: `sudo systemctl restart schedule.service` 
6. Run bot 
```
  python3 bot.py
```

## My unsuccessful attemps to run it

I tried 
- [Render}(https://dashboard.render.com) but Backgrouhd worker only fee-paying
- [Shitob](https://app.shitob.cloud/dashboard) where the number of free minutes have ended

  For this way you need to clone repository and use 3, 4, 6 steps  
  Sounds great for a while...

## Author me and all the knowledge of mankind 
---
So here all information you need to run your bot ~~for mass coups~~
