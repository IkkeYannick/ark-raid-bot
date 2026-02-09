# ARK Raid Alert Bot

This is a Discord bot that watches an ARK tribe log channel and sends alerts when a raid message is detected.

It looks for messages that contain:
For the location:
```
<<ALERT>> LOCATION <<ALERT>>
```
And for the enemy type:
```
by an enemy dino<
```
When found, the bot:
- Pings a role
- Shows where the raid is happening (location)
- Shows who triggered it (enemy type)
- Sends an image
- Tracks how many alerts happened in the last 30 minutes (To determine if it is an actual raid or not.)

---

## Features

- Detects raid alerts from ARK tribe logs
- Extracts the base location (for example MAINWALL)
- Extracts the attacker type (enemy dino or enemy player)
- Pings a Discord role
- Sends an image with the alert
- Keeps a 30 minute rolling raid counter
- Shows danger level using symbols

---

## Requirements

- Python 3.10 or newer
- A Discord bot token
- The bot must be added to your Discord server
- The tribe log must be sent into a Discord channel (even by another bot)

---

## Setup

### 1. Install Python packages
```terminal
python -m pip install discord.py python-dotenv
```
---

### 2. Create a .env file

In the same folder as RaidBot.py, create a file named:

.env

Put this inside (replace the numbers with your own):
```env 
DISCORD_TOKEN=YOUR_BOT_TOKEN
TRIBE_LOG_CHANNEL_ID=123456789012345678
ALERT_CHANNEL_ID=123456789012345678
TRIBELOG_BOT_ID=123456789012345678
ROLE_ID=123456789012345678
```
---

### 3. Add your alert image

Put a .png image named:

alert.png

in the same folder as the bot.

---

### 4. Run the bot

```python
python RaidBot.py
```

If it works, you should see:

Logged in as ARK Raid Bot

---

## How it works

The bot reads every message in the tribe log channel.

If it finds:
```
[2-9 0:20:37][Gen2] <<ALERT>> MAINWALL <<ALERT>></>  triggered by <RichColor Color="0, 0.5, 0.25, 1">by an enemy dino</>.
```
It will send:
- A role ping
- The location (MAINWALL)
- The attacker (enemy dino)
- The raid counter will go up once
- The alert image 

---

## Tips

- Make sure the bot role is above the role it is pinging
- Give the bot permission to read messages, send messages, and mention roles
- Do not upload your .env file to GitHub
- If your token leaks, reset it in the Discord developer portal

---

## Safety

This bot ignores other bots except the tribe log bot you define in the .env file.
This prevents spam loops and false alerts.

---

## Comming soon:

- Structure destroyed detector ( to see if people are clearing spamm)
- More customization
  

## License

Use this for personal servers only.
You are responsible for how you use it.