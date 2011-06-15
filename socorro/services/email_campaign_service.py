import datetime
import logging

import socorro.lib.util as util
import socorro.lib.config_manager as cm
import socorro.webapi.rest_api_base as rstapi
import socorro.database.database as db
import socorro.lib.datetimeutil as dtutil

logger = logging.getLogger("webapi")

#=================================================================================================================
class EmailCampaignService(rstapi.JsonServiceBase):
  """ Hoopsnake API which retrieves a single campaign
      { campagin: {id: 1, product: 'Firefox', versions: "3.5.10, 4.0b6", signature: "js_foo",
                   start_date: "2010-06-05", end_date: "2010-06-07", author: "guilty@charged.name"}}
  """
  #-----------------------------------------------------------------------------------------------------------------
  required_config = _rc = cm.Namespace()
  _rc.option('smtpHostname',
             doc='The hostname of the SMTP provider',
             default='localhost')
  _rc.option('smtpPort',
             doc='The port of the SMTP provider',
             default=25)
  _rc.option('smtpUsername',
             doc='The username for SMTP providers that require authentication otherwise set to None',
             default=None)
  _rc.option('smtpPassword',
             doc='The password for SMTP providers that require authentication otherwise set to None',
             default=None)
  _rc.option('fromEmailAddress',
             doc='Email Address which is used in the From feild of all emails',
             default='no-reply@crash-stats.mozilla.com')
  _rc.option('unsubscribeBaseUrl',
             doc='The base url for handeling un-subscribe requests. This will be used in email templates',
             default="http://crash-stats.mozilla.com/email/subscription/%s")

  #-----------------------------------------------------------------------------------------------------------------
  def __init__(self, configContext):
    super(EmailCampaign, self).__init__(configContext)
    self.database = db.Database(configContext)

  #-----------------------------------------------------------------------------------------------------------------
  # curl http://localhost:8085/201103/emailcampaigns/campaign/1
  "/201103/emailcampaigns/campaign/{id}"
  uri = '/201103/emailcampaigns/campaign/(.*)'

  #-----------------------------------------------------------------------------------------------------------------
  def get(self, *args):
    " Webpy method receives inputs from uri "
    id = int(args[0])

    connection = self.database.connection()
    try:
      cursor = connection.cursor()
      campaign = None
      counts = None
      cursor.execute("""SELECT id, product, versions, signature,
                               subject, body, start_date, end_date,
                               email_count, author, date_created, status
                        FROM email_campaigns WHERE id = %s """, [id])
      rs = cursor.fetchone()
      if rs:
        id, product, versions, signature, subject, body, start_date, end_date, email_count, author, date_created, status = rs
        campaign = {'id': id, 'product': product, 'versions': versions,
                    'signature': signature, 'subject': subject, 'body': body,
                    'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(),
                    'email_count': email_count, 'author': author, 'date_created': date_created.isoformat(), 'status': status, 'send': True}

      cursor.execute("""SELECT count(status), status FROM email_campaigns_contacts
                        WHERE email_campaigns_id = %s
                        GROUP BY status""", [id])
      counts = cursor.fetchall()

      return {'campaign': campaign, 'counts': counts}
    finally:
      connection.close()
