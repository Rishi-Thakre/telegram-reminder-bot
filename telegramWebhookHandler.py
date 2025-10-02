import os
import json
import re
import random # Imported for varied responses
import boto3
import urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from boto3.dynamodb.conditions import Key

# --- AWS Clients ---
dynamo = boto3.resource('dynamodb')
ssm = boto3.client('ssm')

# --- Configuration ---
TIMEZONE = "Asia/Kolkata"
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "Reminders")
IST = ZoneInfo(TIMEZONE)

# --- UI/UX Enhancements ---
FRIENDLY_CONFIRMATIONS = [
    "✅ Got it! I'll remind you.",
    "👍 On it! Reminder is set.",
    "🗓️ All set! Consider it done.",
    "✨ Perfect! I've scheduled that for you.",
    "👌 Reminder locked in!",
]

# --- Load BOT_TOKEN ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    try:
        BOT_TOKEN = ssm.get_parameter(
            Name="/telegram/bot_token",
            WithDecryption=True
        )["Parameter"]["Value"]
    except Exception as e:
        print("❌ Failed to fetch BOT_TOKEN from SSM:", e)
        BOT_TOKEN = None

# --- DynamoDB Table ---
table = dynamo.Table(DYNAMODB_TABLE)

# --- Telegram Helper ---
def send_message(chat_id, text, parse_mode=None):
    """Send a message to the Telegram user."""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN is not set — cannot send message")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print("✅ Telegram API Response:", resp.read().decode())
    except Exception as e:
        print("❌ Telegram API error:", e)

# --- New Helper Function for Better UX ---
def get_friendly_time_string(dt_object, now):
    """Generates a human-readable string like 'Tomorrow at 9:00 AM'."""
    delta = (dt_object.date() - now.date()).days
    time_str = dt_object.strftime('%I:%M %p').lstrip('0') # e.g., "9:30 AM"

    if delta == 0:
        return f"Today at {time_str}"
    elif delta == 1:
        return f"Tomorrow at {time_str}"
    else:
        # e.g., "on Tuesday, Aug 12"
        return f"on {dt_object.strftime('%A, %b %d')} at {time_str}"

# --- Reminder Parser ---
def parse_reminder_command(command_text):
    """
    Parses reminder commands using specific, efficient regular expressions.
    This final version fixes a bug in the return statement.
    """
    command_body = command_text[len("/remind"):].strip()

    # Use the more flexible 'early' regex from the previous version
    early_minutes = 0
    p_early = r'\b(early(\s+reminder)?)\s+(?P<value>\d+)(\s+(min|mins|minute|minutes))?\b'
    early_match = re.search(p_early, command_body, re.IGNORECASE)
    if early_match:
        early_minutes = int(early_match.group('value'))
        command_body = command_body.replace(early_match.group(0), "").strip()

    if not command_body:
        raise ValueError("Cannot set a reminder with no text or time.")

    now = datetime.now(IST)
    task_text = command_body
    target_dt = None
    
    # A single, robust regex for parsing time
    time_regex_str = r'(?P<time>\d{1,2}:\d{2}\s*[ap]m|\d{1,2}:\d{2}|\d{1,2}\s*[ap]m)'

    # --- Parsing Logic ---
    # Pattern 1: "in X minutes/hours"
    p_in_x = r'(?P<matched_text>in\s+(?P<value>\d+)\s+(?P<unit>minute|min|hour|hr)s?)\s*$'
    match = re.search(p_in_x, command_body, re.IGNORECASE)
    if match:
        value = int(match.group('value'))
        unit = match.group('unit').lower()
        if unit.startswith("min"):
            target_dt = now + timedelta(minutes=value)
        else: # hour
            target_dt = now + timedelta(hours=value)
        task_text = command_body[:match.start()].strip()

    # Pattern 2: Absolute Date with Month Name
    if not target_dt:
        months_regex = r'January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec'
        p_month_date = (
            r'(?P<matched_text>(on\s+)?(?P<day>\d{1,2})(st|nd|rd|th)?\s+(?P<month>' + months_regex + r')(\s+(?P<year>\d{4}))?'
            r'(\s+at\s+' + time_regex_str + r')?)\s*$'
        )
        match = re.search(p_month_date, command_body, re.IGNORECASE)
        if match:
            task_text = command_body[:match.start()].strip()
            day = int(match.group('day'))
            month_str = match.group('month')[:3].capitalize()
            year = int(match.group('year')) if match.group('year') else now.year
            month_num = datetime.strptime(month_str, '%b').month
            target_date = datetime(year, month_num, day).date()
            hour, minute = 0, 0
            time_str_match = match.group('time')
            if time_str_match:
                time_str = time_str_match.lower()
                is_pm = "pm" in time_str; is_am = "am" in time_str
                time_str = re.sub(r'\s*(am|pm)', '', time_str)
                if ":" in time_str: parts = time_str.split(":"); hour, minute = int(parts[0]), int(parts[1])
                else: hour, minute = int(time_str), 0
                if is_pm and hour < 12: hour += 12
                if is_am and hour == 12: hour = 0
            target_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=IST).replace(hour=hour, minute=minute)

    # Pattern 3: Absolute Numeric Date
    if not target_dt:
        p_abs_date = r'(?P<matched_text>(on\s+)?(?P<date>\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})(\s+at\s+' + time_regex_str + r')?)\s*$'
        match = re.search(p_abs_date, command_body, re.IGNORECASE)
        if match:
            task_text = command_body[:match.start()].strip()
            date_str = match.group('date').replace('/', '-')
            try: target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError: target_date = datetime.strptime(date_str, '%d-%m-%Y').date()
            hour, minute = 0, 0
            time_str_match = match.group('time')
            if time_str_match:
                time_str = time_str_match.lower()
                is_pm = "pm" in time_str; is_am = "am" in time_str
                time_str = re.sub(r'\s*(am|pm)', '', time_str)
                if ":" in time_str: parts = time_str.split(":"); hour, minute = int(parts[0]), int(parts[1])
                else: hour, minute = int(time_str), 0
                if is_pm and hour < 12: hour += 12
                if is_am and hour == 12: hour = 0
            target_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=IST).replace(hour=hour, minute=minute)

    # Pattern 4: Relative Day and Time
    if not target_dt:
        p_day_time = (
            r'(?P<matched_text>(on|next|at)\s+)?(?P<day>monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
            r'tomorrow|today|day\s+after\s+tomorrow)'
            r'(\s+at\s+' + time_regex_str + r')?\s*$'
        )
        match = re.search(p_day_time, command_body, re.IGNORECASE)
        if match:
            task_text = command_body[:match.start()].strip()
            day_str = match.group('day').lower()
            target_date = now.date()
            if day_str == "tomorrow": target_date += timedelta(days=1)
            elif day_str == "day after tomorrow": target_date += timedelta(days=2)
            elif day_str != "today":
                days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                day_offset = (days.index(day_str) - now.weekday() + 7) % 7
                if day_offset == 0: # If the matched day is today
                  # If the user said "next" or "on", they mean a week from now.
                  # If they just said the day (e.g., "Monday"), they mean today.
                  if 'next' in match.group(0).lower() or 'on' in match.group(0).lower():
                      day_offset = 7
                target_date += timedelta(days=day_offset)
            hour, minute = 0, 0
            time_str_match = match.group('time')
            if time_str_match:
                time_str = time_str_match.lower()
                is_pm = "pm" in time_str; is_am = "am" in time_str
                time_str = re.sub(r'\s*(am|pm)', '', time_str)
                if ":" in time_str: parts = time_str.split(":"); hour, minute = int(parts[0]), int(parts[1])
                else: hour, minute = int(time_str), 0
                if is_pm and hour < 12: hour += 12
                if is_am and hour == 12: hour = 0
            target_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=IST).replace(hour=hour, minute=minute)

    # Pattern 5: Time only
    if not target_dt:
        p_time_only = r'(?P<matched_text>(at\s+)?' + time_regex_str + r')\s*$'
        match = re.search(p_time_only, command_body, re.IGNORECASE)
        if match:
            task_text = command_body[:match.start()].strip()
            time_str = match.group('time').lower()
            is_pm = "pm" in time_str; is_am = "am" in time_str
            time_str = re.sub(r'\s*(am|pm)', '', time_str)
            if ":" in time_str: parts = time_str.split(":"); hour, minute = int(parts[0]), int(parts[1])
            else: hour, minute = int(time_str), 0
            if is_pm and hour < 12: hour += 12
            if is_am and hour == 12: hour = 0
            potential_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if potential_dt <= now:
                potential_dt += timedelta(days=1)
            target_dt = potential_dt

    if not target_dt:
        raise ValueError("I couldn't figure out the time. Try being more specific, like 'tomorrow at 5pm' or 'in 2 hours'.")

    # --- FINAL PROCESSING ---
    target_dt = target_dt.replace(second=0, microsecond=0)
    if target_dt <= now.replace(second=0, microsecond=0):
        raise ValueError("Oops! That time is in the past. Please set a reminder for the future.")

    # **BUG FIX**: Added 'early_minutes' back to the return statement.
    return task_text or "Reminder", target_dt, early_minutes

# --- Main Lambda Handler ---
def lambda_handler(event, context):
    print("📩 Incoming Event:", json.dumps(event))
    try:
        body = json.loads(event['body'])
        message = body.get('message', {})
        chat_id = str(message.get('chat', {}).get('id'))
        text = message.get('text', '').strip()

        if not text:
            send_message(chat_id, "⚠️ Empty message received.")
            return {"statusCode": 200}

        if text.startswith('/remind'):
            try:
                # --- ADD THESE 3 LINES ---
                if len(text.split()) < 2:
                    raise ValueError("Cannot set an empty reminder.\n\nYou can set a reminder like this: \n `/remind Call mom tomorrow at 7pm`")
                # --- END OF ADDED CODE ---
                
                reminder_text, reminder_time_local, early_minutes = parse_reminder_command(text)
                
                # --- **IMPROVED** UI/UX for confirmation message ---
                friendly_intro = random.choice(FRIENDLY_CONFIRMATIONS)
                
                # Use the helper function for a human-readable time string
                now = datetime.now(IST)
                friendly_time = get_friendly_time_string(reminder_time_local, now)
                
                # The precise time for the confirmation body
                ist_time_str = reminder_time_local.strftime('%Y-%m-%d %H:%M')
                
                confirm_msg = (f"{friendly_intro}\n\n"
                               f"📝 *{reminder_text}*\n"
                               f"⏰ {friendly_time} (`{ist_time_str} IST`)")
                
                if early_minutes:
                    confirm_msg += f"\n⏳ You'll get a heads-up *{early_minutes} minutes* before."

                # --- THIS IS THE UPDATED BLOCK ---

                # Save to DB with UTC time
                reminder_time_utc = reminder_time_local.astimezone(timezone.utc)
                item = {
                    'user_id': chat_id,
                    'reminder_time': reminder_time_utc.isoformat(),
                    'reminder_text': reminder_text,
                    'status': 'PENDING'
                }
                if early_minutes:
                    item['early_reminder_minutes'] = early_minutes
                    # NEW: Calculate and store the early reminder time for the GSI
                    early_time_utc = reminder_time_utc - timedelta(minutes=early_minutes)
                    item['early_reminder_time'] = early_time_utc.isoformat()
                    item['early_status'] = 'PENDING'
                
                table.put_item(Item=item)
                send_message(chat_id, confirm_msg, parse_mode="Markdown")

            except ValueError as e:
                # The existing except block will now catch our new error message
                send_message(chat_id, f"😕 Whoops! {str(e)}", parse_mode="Markdown")

        elif text.startswith('/list'):
            res = table.query(KeyConditionExpression=Key('user_id').eq(chat_id))
            reminders = res.get('Items', [])
            
            if not reminders:
                send_message(chat_id, "📭 Your reminder list is empty! Use `/remind` to add one.")
                return {"statusCode": 200}

            reminders.sort(key=lambda x: x['reminder_time'])
            
            lines = ["🗓️ *Your Upcoming Reminders*\n"]
            now = datetime.now(IST)
            last_date_str = None

            for i, r in enumerate(reminders, start=1):
                local_time = datetime.fromisoformat(r['reminder_time']).astimezone(IST)
                
                # --- Grouping Logic ---
                delta = (local_time.date() - now.date()).days
                if delta == 0:
                    current_date_str = "Today"
                elif delta == 1:
                    current_date_str = "Tomorrow"
                else:
                    current_date_str = local_time.strftime('%A, %b %d')

                # Add a day header if it's the first reminder for that day
                if current_date_str != last_date_str:
                    lines.append(f"\n*— {current_date_str} —*")
                    last_date_str = current_date_str
                
                # --- Improved Formatting for each reminder ---
                time_str = local_time.strftime('%I:%M %p').lstrip('0')
                lines.append(f"`{i}.` {r['reminder_text']} 🕒 _{time_str}_")

            # --- Add the helpful footer ---
            lines.append("\n\n- - - - - - - - - - - - - - -")
            lines.append("_To delete a reminder, use `/delete <number>`._")
            
            send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif text.startswith('/delete'):
             parts = text.split()
             if len(parts) != 2 or not parts[1].isdigit():
                 send_message(chat_id, "⚠️ **Oops!** To delete, use the format: `/delete <number>`.\nRun `/list` to see the numbers.", parse_mode="Markdown")
                 return {"statusCode": 200}
             delete_index = int(parts[1])
             res = table.query(KeyConditionExpression=Key('user_id').eq(chat_id))
             reminders = res.get('Items', [])
             if not reminders or delete_index < 1 or delete_index > len(reminders):
                 send_message(chat_id, "❌ That's not a valid reminder number. Try `/list` first!")
                 return {"statusCode": 200}
             reminders.sort(key=lambda x: x['reminder_time'])
             to_delete = reminders[delete_index - 1]
             table.delete_item(Key={'user_id': to_delete['user_id'], 'reminder_time': to_delete['reminder_time']})
             send_message(chat_id, f"🗑️ Got it. I've deleted the reminder for: *{to_delete['reminder_text']}*", parse_mode="Markdown")

        elif text.startswith('/help'):
            help_msg = (
                "*Need help? Here's everything I can do!* ✨\n\n"
                "--- *Basic Commands* ---\n"
                "• /remind <task> <date, time> - Sets a new reminder.\n"
                "• /list - Shows all your upcoming reminders.\n"
                "• /delete <number> - Deletes a reminder from your list.\n\n"
                "--- *Supported Time Formats* ---\n"
                "I understand a variety of time formats. Here are some examples of what works perfectly:\n\n"
                "🗓️ *Dates & Weekdays <date, time>*\n"
                "`tomorrow at 5pm`\n"
                "`on Tuesday at 10:30am`\n"
                "`16 August at 2pm`\n"
                "`15-08-2025 at 11:00`\n"
                "`2026-01-20`\n\n"
                "⏱️ *Relative Times*\n"
                "_Note: Only `minutes` and `hours` are supported._\n"
                "`in 30 minutes`\n"
                "`in 5 hours`\n\n"
                "⏳ *Early Reminders*\n"
                "Want a heads-up? Just add `early` to your command.\n\n For example:\n"
                "`/remind Project deadline at 5pm early 15`\n"
                "`/remind Call mom tomorrow early 30 minutes`\n"
                "`/remind Meeting on Friday at 10am early reminder 10`"
            )
            send_message(chat_id, help_msg, parse_mode="Markdown")

        elif text.startswith('/start'):
            welcome_msg = (
                "👋 *Hi there! I'm your friendly Reminder Bot.* 🤖\n\n"
                "I can help you remind anything, big or small. Just tell me what to remind you of and when.\n\n"
                "• To set a reminder, use `/remind` <task> <date, time>.\n"
                "• To see your list, use /list.\n\n"
                "For a full guide with all the cool time formats I understand, just type /help!"
            )
            send_message(chat_id, welcome_msg, parse_mode="Markdown")
             
        else:
            send_message(chat_id, "🤔 Hmm, I don't recognize that command. Try `/start` to see what I can do!")

        return {"statusCode": 200}
    except Exception as e:
        print("❌ Error in lambda_handler:", str(e))
        return {"statusCode": 500, "body": json.dumps("Error processing request")}
