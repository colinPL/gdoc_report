#!/opt/local/bin/python

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
    return config_data

def send_email(content, config):
    today = datetime.date.today()
    mail_user = config['user']
    mail_pass = config['pass']
    from_adr  = config['from']
    to_adr    = config['to']
    subject   = config['subject'] + ' ' + today.isoformat()
    
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

    flags = tools.argparser.parse_args(args=[])
    CLIENT_SECRET_FILE = 'client_secrets2.json'
    OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'

    config_data = read_config(config_file)
    fileid = config_data['fileid']

    # Setup flow object for auth
    FLOW = flow_from_clientsecrets(CLIENT_SECRET_FILE, scope=OAUTH_SCOPE)

    # Try to get save credentials
    storage = Storage('drive.dat')
    credentials = storage.get()

    # If credentials is None, run through the client auth 
    if credentials is None:
        credentials = tools.run_flow(FLOW, storage, flags)
    
    # Create an httplib2.Http object to handle our HTTP requests
    http = httplib2.Http()
    http = credentials.authorize(http)
    service = build('drive', 'v2', http=http)

    drive_file = service.files().get(fileId=fileid).execute()
    content = download_file(service, drive_file)
    send_email(content, config_data)

if __name__ == "__main__":
   main(sys.argv[1:])
