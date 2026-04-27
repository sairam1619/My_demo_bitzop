import json
from datetime import datetime
import boto3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz

RECIPIENT = ["ramu@datadelivers.com"]
SENDER = "Datadelivers CMP <noreply@cmp.io>"
CHARSET = "UTF-8"
ses_client = boto3.client('ses', region_name="us-west-2")
dynamodb = boto3.resource('dynamodb')
email_status_table = dynamodb.Table("cmp-query-status")

def lambda_handler(event, context):
    print("Event:", event)
    aws_account_id = context.invoked_function_arn.split(":")[4]
    env = 'Dev' if aws_account_id == '743020291706' else 'Prod'
    client_name = event['client_name']
    processing_date = event['processing_date']
    table_name = event['table_name']
    present_date = datetime.today().strftime("%Y-%m-%d")

    if table_name == 'IbHouseholdAggregate':
        SUBJECT = f"{env}: Intellibase Household Aggregate Step Function Completed Successfully on {present_date}"
        thread_type = "ib_household_thread"
    else:
        SUBJECT = f"{env}: IB Update Step Function Completed Successfully on {present_date}"
        thread_type = "ib_update_thread"

    BODY = f"{table_name} creation is successful for {client_name} on {present_date} (processing_date: {processing_date})"
    print(f"Subject: {SUBJECT}")

    try:
        current_time = datetime.now(pytz.timezone('America/Chicago'))
        current_date = str(current_time.date())
        print(f"current_time is {current_time}")

        dynamo_response = email_status_table.get_item(Key={"client_id": "email_thread"})
        if "Item" in dynamo_response:
            item = dynamo_response["Item"]
        else:
            item = {}

        if thread_type in item:
            thread_message_id = item[thread_type]["msg_id"]
            thread_date = item[thread_type]["thread_date"]
        else:
            thread_message_id = ""
            thread_date = ""

        if thread_date != current_date:
            thread_message_id = ""

        msg = MIMEMultipart()
        msg["Subject"] = SUBJECT
        msg["From"] = SENDER
        msg["To"] = ", ".join(RECIPIENT)

        if thread_message_id != "":
            msg["In-Reply-To"] = thread_message_id
            msg["References"] = thread_message_id

        msg.attach(MIMEText(BODY, "plain"))

        response = ses_client.send_raw_email(
            Source=SENDER,
            Destinations=RECIPIENT,
            RawMessage={"Data": msg.as_bytes()}
        )

        message_id = response["MessageId"]

        email_status_table.update_item(
            Key={"client_id": "email_thread"},
            UpdateExpression="SET " + thread_type + ".msg_id = :m, " + thread_type + ".thread_date = :d",
            ExpressionAttributeValues={":m": message_id, ":d": current_date}
        )

    except Exception as e:
        print("Error while sending email or updating DynamoDB:", str(e))
        raise e
    else:
        print("Email sent successfully! Message ID:", message_id)
    print("Email Sent")