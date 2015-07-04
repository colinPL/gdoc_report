#!/usr/bin/env python

import re
import sys
import json
import getopt
import smtplib
import httplib2
import argparse
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apiclient import errors
from apiclient.discovery import build
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets

CLIENT_SECRET_FILE = 'client_secrets2.dat'
OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive.file'


def update_pooler_stats(content):
    today = datetime.date.today()
    datedelta = datetime.timedelta(days=-1)
    yesterday = str(today + datedelta)
    yesterday_str = yesterday.strftime('%A, %b %d') # Thursday, Apr 09
    poolerstats = {}

    http = httplib2.Http()
    (headers, response) = http.request("http://vmpooler.delivery.puppetlabs.net/api/v1/summary?from=" + yesterday + "&to=" + yesterday)

    response_json = json.loads(response)

    poolerstats['numclones'] = response_json['daily'][0]['clone']['count']['total']
    poolerstats['clonetime'] = response_json['daily'][0]['clone']['duration']['average']

    try:
      new_content = content
      new_content = re.sub("24 hour summation of VMPooler cloned VMs: POOLER_CLONES", 'Number of VMPooler VMs cloned for ' + yesterday_str + ': ' + str(poolerstats['numclones']), new_content)
      new_content = re.sub("Average clone time per VM \(sec\): POOLER_TIMES", 'Average clone time per VM (sec): ' + str(poolerstats['clonetime']), new_content)
      return new_content
    except:
      return content


def download_file(service, drive_file):
    download_url = drive_file['exportLinks']['text/html']
    if download_url:
        resp, content = service._http.request(download_url)
        if resp.status == 200:
            return content
        else:
            print 'An error occurred: %s' % resp
            return None
    else:
      print "can't seem to find any data"
      return None


def read_config(config_file):
    with open(config_file) as json_data:
        config_data = json.load(json_data)
        json_data.close()
    with open('mail_creds.dat') as json_data:
        creds = json.load(json_data)
        json_data.close()
    config_data.update(creds)
    return config_data


def parse_args(argv):
    if len(sys.argv) < 2:
        print 'send_gdoc.py -c <configfile>'
        sys.exit()
    try:
        opts, args = getopt.getopt(argv,"hc:",["cfg="])
    except getopt.GetoptError:
        print 'send_gdoc.py -c <configfile>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'send_gdoc.py -c <configfile>'
            sys.exit()
        elif opt in ("-c", "--cfg"):
            config_file = arg
    return config_file


def send_email(content, config):
    today = datetime.date.today()
    mail_user = config['user']
    mail_pass = config['pass']
    from_adr  = config['from']
    to_adr    = config['to']
    subject   = today.isoformat() + ' ' + config['subject']

    message = MIMEMultipart('alternative')
    message['Subject'] = subject
    message['From'] = mail_user
    message['To'] = to_adr
    part1 = MIMEText(content, 'html')
    message.attach(part1)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(mail_user, mail_pass)
        server.sendmail(from_adr, to_adr, message.as_string())
        server.quit()
        print 'successfully sent the mail'
    except smtplib.SMTPAuthenticationError as e:
       print "Unable to send message: %s" % e


############### Main ####################
def main(argv):

    config_file = parse_args(argv)
    config_data = read_config(config_file)
    fileid = config_data['fileid']

    # Setup flow object for auth
    flow = flow_from_clientsecrets(CLIENT_SECRET_FILE, scope=OAUTH_SCOPE)

    # Try to get saved credentials
    storage = Storage('drive.dat')
    credentials = storage.get()

    # If credentials is None, run through the client auth
    if credentials is None:
        credentials = tools.run_flow(flow, storage, flags)

    # Create an httplib2.Http object to handle our HTTP requests
    http = httplib2.Http()
    http = credentials.authorize(http)
    service = build('drive', 'v2', http=http)

    drive_file = service.files().get(fileId=fileid).execute()
    content = download_file(service, drive_file)
    content = update_pooler_stats(content)
    send_email(content, config_data)

if __name__ == "__main__":
   main(sys.argv[1:])
