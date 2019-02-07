import cherrypy
import splunk.appserver.mrsparkle.controllers as controllers
from splunk.appserver.mrsparkle.lib.decorators import expose_page
from splunk.appserver.mrsparkle.lib.routes import route
import json
import urllib
import urllib2
from plaid_modular_input import ModInputplaid_modular_input
from splunk_aoblib.setup_util import Setup_Util
from splunk.clilib import cli_common as cli

class AccessTokenController(controllers.BaseController):
	@expose_page(must_login=True)
	def listenerPost(self, **kwargs):
		cherrypy.response.headers['Content-Type'] = 'text/plain'
		# Get arguments
		publictoken = kwargs["public_token"]
		splunkd_session = cherrypy.request.cookie["splunkd_8000"].value

		# Sometimes I look at my code and think "What did I just do?"
		# This is one of those moments
		# Though really what I think I did is hijack the modular input class definition, create its setup_util attribute using the Setup_Util constructor, and then pull the necessary decrypted attributes
		helper = ModInputplaid_modular_input()
		helper.setup_util = Setup_Util("https://127.0.0.1:8089", splunkd_session, helper.logger)
		enable_development_mode = helper.get_global_setting("enable_development_mode_")

		mode = "sandbox"
		if enable_development_mode.isdigit():
			if int(enable_development_mode) == 1:
				mode = "development"

		# API Credentials
		clientid = helper.get_global_setting("client_id")
		client_secret = helper.get_global_setting("client_secret_%s_" % mode)

		# Set the base URL
		base_url = "https://%s.plaid.com" % mode

		# Our json request body, exchange the public token for an access_token
		data = {
			'client_id': clientid,
			'secret': client_secret,
			'public_token': publictoken
		}

		# Exchange our public token for an access token
		req = urllib2.Request('%s/item/public_token/exchange' % base_url, json.dumps(data), headers={'Content-type': 'application/json', 'Accept': 'application/json'})
		response = urllib2.urlopen(req)
		return response.read()

	@expose_page(must_login=True)
	def returnPublicInfo(self, **kwargs):
		cfg = cli.getConfStanza('ta_plaid_settings','additional_parameters')
		publickey = cfg.get('public_key')
		enable_development_mode = cfg.get('enable_development_mode_')
		mode = "sandbox"
		if enable_development_mode.isdigit():
			if int(enable_development_mode) == 1:
				mode = "development"
		data = {
			'public_key': publickey,
			'environment': mode
		}

		return json.dumps(data)