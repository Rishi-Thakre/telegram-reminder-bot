import os
import json
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import boto3
import random
from boto3.dynamodb.conditions import Key

# --- AWS Clients ---
dynamo = boto3.resource('dynamodb')
ssm = boto3.client('ssm')

# --- Configuration ---
TIMEZONE = "Asia/Kolkata"
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "Reminders")
IST = ZoneInfo(TIMEZONE)

# --- UI/UX Enhancements ---
FINAL_REMINDER_INTROS = [
    "🔔 Reminder!", "⏰ It's time!", 
    "✅ Time for your reminder!", "🗓️ Here's that reminder you set:",
]

# --- Load BOT_TOKEN ---
BOT_TOKEN = ssm.get_parameter(Name='/telegram/bot_token', WithDecryption=True)['Parameter']['Value']

# --- DynamoDB Table ---
table = dynamo.Table(DYNAMODB_TABLE)

# --- Telegram Helper ---
def send_telegram_message(chat_id, text, parse_mode=None):
    """Sends a simple text message without buttons."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"✅ Sent message to {chat_id}. Response: {resp.read().decode()}")
    except Exception as e:
        print(f"❌ Telegram API error for chat_id {chat_id}: {e}")

def process_early_reminders(now_utc_iso):
    """Queries for and sends due early reminders."""
    print(f"Querying for early reminders due before {now_utc_iso}...")
    try:
        early_reminders = table.query(
            IndexName='EarlyStatusAndTimeIndex',
            KeyConditionExpression=Key('early_status').eq('PENDING') & Key('early_reminder_time').lt(now_utc_iso)
        ).get('Items', [])
    except Exception as e:
        print(f"❌ Error querying EarlyStatusAndTimeIndex: {e}")
        return

    print(f"Found {len(early_reminders)} early reminders to send.")
    for r in early_reminders:
        user_id = r['user_id']
        reminder_time = r['reminder_time']
        minutes = int(r['early_reminder_minutes'])

        final_time_utc = datetime.fromisoformat(reminder_time)
        final_time_local_str = final_time_utc.astimezone(IST).strftime('%I:%M %p').lstrip('0')

        # --- **IMPROVED** UI/UX for the early reminder message ---
        message = (
            f"⏳ *Heads-up! Your reminder is in {minutes} minutes.*\n\n"
            f"📝 *Task:* {r['reminder_text']}\n"
            f"⏰ *Time:* {final_time_local_str}"
        )
        
        send_telegram_message(user_id, message, parse_mode="Markdown")
        
        # Update the item to remove the early status so it's not sent again
        table.update_item(
            Key={'user_id': user_id, 'reminder_time': reminder_time},
            UpdateExpression="REMOVE early_status, early_reminder_time"
        )
        print(f"  > Sent and updated early reminder for user {user_id}.")

def process_final_reminders(now_utc_iso):
    """Queries for and sends due final reminders."""
    print(f"Querying for final reminders due before {now_utc_iso}...")
    try:
        final_reminders = table.query(
            IndexName='StatusAndTimeIndex',
            KeyConditionExpression=Key('status').eq('PENDING') & Key('reminder_time').lt(now_utc_iso)
        ).get('Items', [])
    except Exception as e:
        print(f"❌ Error querying StatusAndTimeIndex: {e}")
        return

    print(f"Found {len(final_reminders)} final reminders to send.")
    for r in final_reminders:
        user_id = r['user_id']
        reminder_time = r['reminder_time']
        
        intro = random.choice(FINAL_REMINDER_INTROS)
        message = f"{intro}\n\n📝 *{r['reminder_text']}*"
        send_telegram_message(user_id, message, parse_mode="Markdown")
        
        # Delete the reminder after sending
        table.delete_item(
            Key={'user_id': user_id, 'reminder_time': reminder_time}
        )
        print(f"  > Sent and deleted final reminder for user {user_id}.")

# --- Main Lambda Handler for the Sender ---
def lambda_handler(event, context):
    print("🚀 Reminder sender function triggered.")
    now_utc_iso = datetime.now(timezone.utc).isoformat()
    
    try:
        process_early_reminders(now_utc_iso)
        process_final_reminders(now_utc_iso)
        
        print("✅ Sender function finished successfully.")
        return {"statusCode": 200, "body": json.dumps("Reminders processed successfully.")}
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        return {"statusCode": 500, "body": json.dumps("Error processing reminders.")}
