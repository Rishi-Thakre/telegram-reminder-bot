# 🤖 Serverless Telegram Reminder Bot

A powerful, serverless reminder bot for Telegram built entirely on AWS. It uses natural language processing to understand dates and times, allowing you to set, list, and manage reminders with ease.

[![Telegram Bot](https://img.shields.io/badge/Telegram-@GetReminder_bot-blue.svg?style=for-the-badge&logo=telegram)](https://t.me/GetReminder_bot)



---

## ✨ Features

* **Natural Language Parsing:** Set reminders like a human! E.g., `/remind Call mom tomorrow at 7pm`.
* **Flexible Time Formats:** Understands various formats:
    * Relative: `in 30 minutes`, `in 2 hours`
    * Specific: `at 5pm`, `10:30am`
    * Dates: `on Tuesday`, `15 August`, `2025-12-25`
* **Early Reminders:** Get a heads-up before your actual reminder. E.g., `...early 15 minutes`.
* **CRUD Operations:** Create, list, and delete your reminders.
* **Serverless Architecture:** Built with AWS Lambda, DynamoDB, and API Gateway for scalability and cost-efficiency.
* **Secure:** Your Telegram Bot Token is securely stored in AWS Systems Manager Parameter Store.

---

## 🚀 Live Demo

You can try the bot live on Telegram: **[@GetReminder_bot](https://t.me/GetReminder_bot)**

---

## 🛠️ How It Works: Architecture

This bot operates on a fully serverless architecture, ensuring it's both efficient and cost-effective.


<img width="3000" height="2500" alt="image" src="https://github.com/user-attachments/assets/6566b35a-63f3-457d-83f8-1ad3983b472c" />

[Image of a serverless architecture diagram]


1.  **User Interaction:** You send a command (e.g., `/remind`) to the bot on Telegram.
2.  **Webhook Trigger:** Telegram forwards your message to an **API Gateway** endpoint.
3.  **Processing (Lambda #1):** The API Gateway triggers the `telegramWebhookHandler` AWS Lambda function. This function parses your message, validates it, and saves the reminder details to a **DynamoDB** table. It then sends a confirmation message back to you.
4.  **Scheduled Check (EventBridge):** An **Amazon EventBridge** rule is set to trigger the `reminderSender` AWS Lambda function every minute.
5.  **Sending Reminders (Lambda #2):** The `reminderSender` function queries the DynamoDB table for any reminders that are due.
6.  **Notification:** If a due reminder is found, the function sends a notification to you via the Telegram Bot API and updates or deletes the entry in DynamoDB.

---

## 👨‍💻 Bot Commands

Here's what the bot can do:

| Command   | Description                                      | Example                                  |
| :-------- | :----------------------------------------------- | :--------------------------------------- |
| **/start** | Displays a welcome message.                      | `/start`                                 |
| **/help** | Shows a detailed guide on commands and formats.  | `/help`                                  |
| **/remind** | Sets a new reminder. Supports natural language.  | `/remind Buy groceries tomorrow at 5pm`    |
| **/list** | Shows all your upcoming reminders.               | `/list`                                  |
| **/delete** | Deletes a specific reminder by its number.       | `/delete 3`                              |

---

## ⚙️ Setup and Deployment Guide

Follow these steps to deploy your own instance of the reminder bot.

### Prerequisites

* An **AWS Account**
* A **Telegram Account**

***

### PHASE 1: Initial AWS & Telegram Setup

#### Step 1: Get Your Telegram Bot Token

1.  Open Telegram and search for `@BotFather`.
2.  Send the `/newbot` command.
3.  Follow the instructions to name your bot and choose a username.
4.  **BotFather** will give you a token. **Save this `BOT_TOKEN` securely.**

#### Step 2: Store Bot Token in AWS SSM

1.  Navigate to the **AWS Systems Manager** console.
2.  Go to **Parameter Store** and click **"Create parameter"**.
3.  Use the following details:
    * **Name:** `/telegram/bot_token`
    * **Type:** `SecureString`
    * **Value:** Paste the `BOT_TOKEN` you got from BotFather.
4.  Click **"Create parameter"**.

#### Step 3: Create DynamoDB Table

1.  Navigate to the **Amazon DynamoDB** console.
2.  Click **"Create table"** with the following configuration:
    * **Table name:** `Reminders`
    * **Partition key:** `user_id` (Type: String)
    * **Sort key:** `reminder_time` (Type: String)
3.  After the table is created, go to the **Indexes** tab and create two **Global Secondary Indexes (GSIs)**. These are crucial for querying due reminders efficiently.
    * **Index 1 (For Final Reminders):**
        * **Index name:** `StatusAndTimeIndex`
        * **Partition key:** `status` (Type: String)
        * **Sort key:** `reminder_time` (Type: String)
    * **Index 2 (For Early Reminders):**
        * **Index name:** `EarlyStatusAndTimeIndex`
        * **Partition key:** `early_status` (Type: String)
        * **Sort key:** `early_reminder_time` (Type: String)

***

### PHASE 2: Deploying the Lambda Functions

You will create two separate Lambda functions.

#### Lambda #1: `telegramWebhookHandler`

This function handles incoming messages from users.

1.  Go to the **AWS Lambda** console and click **"Create function"**.
2.  Select **"Author from scratch"**.
3.  **Function name:** `telegramWebhookHandler`
4.  **Runtime:** `Python 3.9` or newer.
5.  **Permissions:** Create a new role with basic Lambda permissions. We will add more permissions later.
6.  Click **"Create function"**.
7.  In the **Code source** editor, paste the provided Python code for `telegramWebhookHandler`.
8.  Go to **Configuration > Environment variables** and add one:
    * **Key:** `DYNAMODB_TABLE`
    * **Value:** `Reminders`

#### Lambda #2: `reminderSender`

This function checks for and sends due reminders.

1.  Create another Lambda function named `reminderSender` using the same steps as above.
2.  Paste the provided Python code for `reminderSender`.
3.  Add the same environment variable:
    * **Key:** `DYNAMODB_TABLE`
    * **Value:** `Reminders`

#### IAM Permissions

Your Lambda functions need permission to talk to other AWS services.

1.  Go to the **IAM** console > **Roles**.
2.  Find the execution role created for your Lambda functions (it will contain the function names).
3.  Attach the following AWS managed policies or create a custom inline policy with these permissions:
    * `AWSLambdaBasicExecutionRole` (usually attached by default)
    * `AmazonDynamoDBFullAccess` (for production, scope this down to the specific `Reminders` table)
    * `AmazonSSMReadOnlyAccess` (to read the bot token from Parameter Store)

***

### PHASE 3: API Gateway & Telegram Webhook

This connects your bot to the `telegramWebhookHandler` Lambda.

1.  Go to the **API Gateway** console and click **"Build"** on the **REST API** card.
2.  Choose **New API**.
3.  **API name:** `telegramWebhookApi`
4.  Click **"Create API"**.
5.  From the **Actions** dropdown, select **"Create Method"**. Choose `POST` and click the checkmark.
6.  For the **Integration type**, select `Lambda Function` and choose your `telegramWebhookHandler` function.
7.  Click **Save**.
8.  From the **Actions** dropdown again, select **"Deploy API"**. Create a new deployment stage (e.g., `prod`).
9.  After deploying, you will get an **Invoke URL**. Copy it.
10. Set the Telegram webhook by running this command in your terminal, replacing `<BOT_TOKEN>` and `<INVOKE_URL>`:
    ```bash
    curl --request POST \
         --url [https://api.telegram.org/bot](https://api.telegram.org/bot)<BOT_TOKEN>/setWebhook \
         --header 'content-type: application/json' \
         --data '{"url": "<INVOKE_URL>"}'
    ```

***

### PHASE 4: Schedule the Reminder Sender

This will run your `reminderSender` function automatically.

1.  Go to the **Amazon EventBridge** console.
2.  Click **"Create rule"**.
3.  **Name:** `ReminderCheckRule`
4.  Select **"Schedule"** and choose a **Fixed rate every `1` minute**.
5.  For the **Target**, select **"AWS Lambda function"** and choose your `reminderSender` function.
6.  Click **"Create"**.

**Congratulations! Your serverless Telegram reminder bot is now fully deployed and operational!** 🎉

---

## 💻 Tech Stack

* **Backend:** Python
* **Cloud Provider:** Amazon Web Services (AWS)
* **Compute:** AWS Lambda
* **Database:** Amazon DynamoDB
* **API:** Amazon API Gateway
* **Scheduling:** Amazon EventBridge
* **Secrets Management:** AWS Systems Manager Parameter Store
