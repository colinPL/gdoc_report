#!/opt/local/bin/python

import re
import sys
import json
import redis
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

def update_pooler_stats(content):
    today = datetime.date.today()
    datedelta = datetime.timedelta(days=-1)
    poolerstats = {}
    r = redis.StrictRedis(host='redis.delivery.puppetlabs.net', port=6379, db=0)
    poolerstats['numclones'] = r.hlen('vmpooler__clone__' + str(today + datedelta))
    poolerstats['clonetime'] = reduce(lambda x, y: x+y, map(float, (r.hvals('vmpooler__clone__' + str(today + datedelta))))) / poolerstats['numclones']

    try:
      new_content = content 
      new_content = re.sub("Total VMs cloned: \d+", 'Total VMs cloned: ' + str(poolerstats['numclones']), new_content)
      new_content = re.sub("Average clone time \(sec\): \d+\.\d+", 'Average clone time (sec): ' + str(poolerstats['clonetime']), new_content)
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
    CLIENT_SECRET_FILE = 'client_secrets2.dat'
    OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive.file'

    config_data = read_config(config_file)
    fileid = config_data['fileid']

    # Setup flow object for auth
    FLOW = flow_from_clientsecrets(CLIENT_SECRET_FILE, scope=OAUTH_SCOPE)

    # Try to get saved credentials
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
    content = update_pooler_stats(content)
    send_email(content, config_data)

if __name__ == "__main__":
   main(sys.argv[1:])
