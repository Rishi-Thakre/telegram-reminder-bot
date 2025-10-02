# telegram-reminder-bot

🤖 Serverless Telegram Reminder Bot
A powerful, serverless reminder bot for Telegram built entirely on AWS. It uses natural language processing to understand dates and times, allowing you to set, list, and manage reminders with ease.

✨ Features
Natural Language Parsing: Set reminders like a human! E.g., /remind Call mom tomorrow at 7pm.

Flexible Time Formats: Understands various formats:

Relative: in 30 minutes, in 2 hours

Specific: at 5pm, 10:30am

Dates: on Tuesday, 15 August, 2025-12-25

Early Reminders: Get a heads-up before your actual reminder. E.g., ...early 15 minutes.

CRUD Operations: Create, list, and delete your reminders.

Serverless Architecture: Built with AWS Lambda, DynamoDB, and API Gateway for scalability and cost-efficiency.

Secure: Your Telegram Bot Token is securely stored in AWS Systems Manager Parameter Store.

🚀 Live Demo
You can try the bot live on Telegram: @GetReminder_bot

🛠️ How It Works: Architecture
This bot operates on a fully serverless architecture, ensuring it's both efficient and cost-effective.

Shutterstock

User Interaction: You send a command (e.g., /remind) to the bot on Telegram.

Webhook Trigger: Telegram forwards your message to an API Gateway endpoint.

Processing (Lambda #1): The API Gateway triggers the telegramWebhookHandler AWS Lambda function. This function parses your message, validates it, and saves the reminder details to a DynamoDB table. It then sends a confirmation message back to you.

Scheduled Check (EventBridge): An Amazon EventBridge rule is set to trigger the reminderSender AWS Lambda function every minute.

Sending Reminders (Lambda #2): The reminderSender function queries the DynamoDB table for any reminders that are due.

Notification: If a due reminder is found, the function sends a notification to you via the Telegram Bot API and updates or deletes the entry in DynamoDB.

👨‍💻 Bot Commands
Here's what the bot can do:

Command	Description	Example
/start	Displays a welcome message.	/start
/help	Shows a detailed guide on commands and formats.	/help
/remind	Sets a new reminder. Supports natural language.	/remind Buy groceries tomorrow at 5pm
/list	Shows all your upcoming reminders.	/list
/delete	Deletes a specific reminder by its number.	/delete 3

Export to Sheets
⚙️ Setup and Deployment Guide
Follow these steps to deploy your own instance of the reminder bot.

Prerequisites
An AWS Account

A Telegram Account

PHASE 1: Initial AWS & Telegram Setup
Step 1: Get Your Telegram Bot Token
Open Telegram and search for @BotFather.

Send the /newbot command.

Follow the instructions to name your bot and choose a username.

BotFather will give you a token. Save this BOT_TOKEN securely.

Step 2: Store Bot Token in AWS SSM
Navigate to the AWS Systems Manager console.

Go to Parameter Store and click "Create parameter".

Use the following details:

Name: /telegram/bot_token

Type: SecureString

Value: Paste the BOT_TOKEN you got from BotFather.

Click "Create parameter".

Step 3: Create DynamoDB Table
Navigate to the Amazon DynamoDB console.

Click "Create table" with the following configuration:

Table name: Reminders

Partition key: user_id (Type: String)

Sort key: reminder_time (Type: String)

After the table is created, go to the Indexes tab and create two Global Secondary Indexes (GSIs). These are crucial for querying due reminders efficiently.

Index 1 (For Final Reminders):

Index name: StatusAndTimeIndex

Partition key: status (Type: String)

Sort key: reminder_time (Type: String)

Index 2 (For Early Reminders):

Index name: EarlyStatusAndTimeIndex

Partition key: early_status (Type: String)

Sort key: early_reminder_time (Type: String)

PHASE 2: Deploying the Lambda Functions
You will create two separate Lambda functions.

Lambda #1: telegramWebhookHandler
This function handles incoming messages from users.

Go to the AWS Lambda console and click "Create function".

Select "Author from scratch".

Function name: telegramWebhookHandler

Runtime: Python 3.9 or newer.

Permissions: Create a new role with basic Lambda permissions. We will add more permissions later.

Click "Create function".

In the Code source editor, paste the provided Python code for telegramWebhookHandler.

Go to Configuration > Environment variables and add one:

Key: DYNAMODB_TABLE

Value: Reminders

Lambda #2: reminderSender
This function checks for and sends due reminders.

Create another Lambda function named reminderSender using the same steps as above.

Paste the provided Python code for reminderSender.

Add the same environment variable:

Key: DYNAMODB_TABLE

Value: Reminders

IAM Permissions
Your Lambda functions need permission to talk to other AWS services.

Go to the IAM console > Roles.

Find the execution role created for your Lambda functions (it will contain the function names).

Attach the following AWS managed policies or create a custom inline policy with these permissions:

AWSLambdaBasicExecutionRole (usually attached by default)

AmazonDynamoDBFullAccess (for production, scope this down to the specific Reminders table)

AmazonSSMReadOnlyAccess (to read the bot token from Parameter Store)

PHASE 3: API Gateway & Telegram Webhook
This connects your bot to the telegramWebhookHandler Lambda.

Go to the API Gateway console and click "Build" on the REST API card.

Choose New API.

API name: telegramWebhookApi

Click "Create API".

From the Actions dropdown, select "Create Method". Choose POST and click the checkmark.

For the Integration type, select Lambda Function and choose your telegramWebhookHandler function.

Click Save.

From the Actions dropdown again, select "Deploy API". Create a new deployment stage (e.g., prod).

After deploying, you will get an Invoke URL. Copy it.

Set the Telegram webhook by running this command in your terminal, replacing <BOT_TOKEN> and <INVOKE_URL>:

Bash

curl --request POST \
     --url https://api.telegram.org/bot<BOT_TOKEN>/setWebhook \
     --header 'content-type: application/json' \
     --data '{"url": "<INVOKE_URL>"}'
PHASE 4: Schedule the Reminder Sender
This will run your reminderSender function automatically.

Go to the Amazon EventBridge console.

Click "Create rule".

Name: ReminderCheckRule

Select "Schedule" and choose a Fixed rate every 1 minute.

For the Target, select "AWS Lambda function" and choose your reminderSender function.

Click "Create".

Congratulations! Your serverless Telegram reminder bot is now fully deployed and operational! 🎉

💻 Tech Stack
Backend: Python

Cloud Provider: Amazon Web Services (AWS)

Compute: AWS Lambda

Database: Amazon DynamoDB

API: Amazon API Gateway

Scheduling: Amazon EventBridge

Secrets Management: AWS Systems Manager Parameter Store
