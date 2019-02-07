# encoding = utf-8

import os
import sys
import time
import datetime
import json
import calendar

def validate_input(helper, definition):
    # It's kinda hard to validate an access token without issuing a request back to Plaid, and I think the less requests there are the better.
    # I rather assume that the Link functionality doesn't break
    pass

def collect_events(helper, ew):

    # All needed data for requests
    input_name = helper.get_input_stanza_names()
    access_token = helper.get_arg('plaid_access_token')
    enable_development_mode = helper.get_global_setting("enable_development_mode_")

    mode = "sandbox"
    if enable_development_mode.isdigit():
        if int(enable_development_mode) == 1:
            mode = "development"

    # API Credentials
    client_id = helper.get_global_setting("client_id")
    client_secret = helper.get_global_setting("client_secret_%s_" % mode)
    
    # Set the base URL
    base_url = "https://%s.plaid.com" % mode
    # Get whether this is the first run of the modular input
    notFirstPull = helper.get_check_point("notFirstPull:" + input_name)
    if notFirstPull:
        handleIntervalPull(helper, ew, input_name, access_token, enable_development_mode, client_id, client_secret, base_url)
    else:
        handleFirstPull(helper, ew, input_name, access_token, enable_development_mode, client_id, client_secret, base_url)

def handleIntervalPull(helper, ew, input_name, access_token, enable_development_mode, clientid, client_secret, base_url):
    # Get current month and year,
    today = datetime.date.today()
    year = today.year
    month = today.month
    
    # Get the last day of the current month
    lastDay = calendar.monthrange(year,month)[1]

    # Format two API-friendly dates for the beginning and end of the month
    start_date = "%s-%s-%s" % (year, '%02d' % month, "01")
    end_date = "%s-%s-%s" % (year, '%02d' % month, lastDay)

    # Our Request Json (dict)
    # Pull all transactions full the current month
    # I'm not really flipping pages here just because I didn't think it was necessary
    # should add in later anyway incase a company monitors their own bank account (which I would assume gets a lot of transactions)
    request_json = {
        "client_id": clientid,
        "secret": client_secret,
        "access_token": access_token,
        "start_date": start_date,
        "end_date": end_date,
        "options": {
            "count": 500,
            "offset": 0
        }
    }

    # Request the transactions for the specified bank
    request_json_string = json.dumps(request_json)
    response = helper.send_http_request("%s/transactions/get" % base_url, "POST", payload=request_json_string,headers={'Content-type': 'application/json', 'Accept': 'application/json'})
    response_json = response.json()

    # For each transaction, add a dummy time to the end of the date. For some reason I couldn't get the sourcetyping right to just get the date alone.
    for index, obj in enumerate(response_json["transactions"]):
        response_json["transactions"][index]["date"] = response_json["transactions"][index]["date"] + " 00:00:00.000"

    # Get the json that was returned for the last run, if there was no last run, just create an empty list
    old_json = helper.get_check_point("oldTransactions:" + input_name)
    if old_json:
        ""
    else:
        old_json = []

    # For each transaction, create an event with the following information
    # source = <input name/bank>:transaction 
    # sourcetype = plaid
    # raw = the json of the transaction
    for transaction in response_json["transactions"]:
        # If the transaction already exists in the old json, that means we already created an event for this transaction, and that we should skip.
        if transaction not in old_json:
            event = helper.new_event(source=("%s:transaction" % input_name), index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data=json.dumps(transaction))
            ew.write_event(event)

    # Save the new list of transactions
    helper.save_check_point("oldTransactions:" + input_name, response_json["transactions"])


    # For each account, create an event with the following information
    # I pull this data everytime because it contains all the balance data for a specified account
    # source = <input name/bank>:account 
    # sourcetype = plaid
    # raw = the json of the account
    for account in response_json["accounts"]:
        event = helper.new_event(source=("%s:account" % input_name), index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data=json.dumps(account))
        ew.write_event(event)
      
def handleFirstPull(helper, ew, input_name, access_token, enable_development_mode, clientid, client_secret, base_url):
    # Get to the previous month before today
    today = datetime.date.today()
    first = today.replace(day=1)
    lastMonth = first - datetime.timedelta(days=1)

    # Get the last day of previous month
    lastDayLastMonth = calendar.monthrange(lastMonth.year,lastMonth.month)[1]

    # Format to be friendly with the API
    end_date = "%s-%s-%s" % (lastMonth.year, '%02d' % lastMonth.month, lastDayLastMonth)

    # The loop counter/exit flag
    offset_count = 0
    pulling = True
    while pulling:

        # Our Request Json (dict)
        # Pull all requests from 1990 to the end of the previous month
        # Offset count is increased if we need to "flip the page" to get to the rest of the results
        request_json = {
            "client_id": clientid,
            "secret": client_secret,
            "access_token": access_token,
            "start_date": "1990-01-01",
            "end_date": end_date,
            "options": {
                "count": 500,
                "offset": offset_count * 500
            }
        }

        # Request the transactions for the specified bank
        request_json_string = json.dumps(request_json)
        response = helper.send_http_request("%s/transactions/get" % base_url, "POST", payload=request_json_string,headers={'Content-type': 'application/json', 'Accept': 'application/json'})
        response_json = response.json()

        # For each transaction, add a dummy time to the end of the date. For some reason I couldn't get the sourcetyping right to just get the date alone.
        for index, obj in enumerate(response_json["transactions"]):
            response_json["transactions"][index]["date"] = response_json["transactions"][index]["date"] + " 00:00:00.000"

        # The number of transactions in the specified time_period, used to figure out if we need to get more "pages"
        total_transactions = response_json["total_transactions"]

        # For each transaction, create an event with the following information
        # source = <input name/bank>:transaction 
        # sourcetype = plaid
        # raw = the json of the transaction
        for transaction in response_json["transactions"]:
            event = helper.new_event(source=("%s:transaction" % input_name), index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data=json.dumps(transaction))
            ew.write_event(event)

        # If there are more transactions than we have currently pulled, increase the "page" number
        # otherwise, stop pulling any more data (exit)
        if total_transactions > (500 * (offset_count + 1)):
            offset_count = offset_count + 1
        else:
            pulling = False

    # We have finished pulling in all data, make sure we know it when we start pulling on regular intervals.
    helper.save_check_point("notFirstPull:" + input_name, True)

