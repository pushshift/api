#!/usr/bin/env python3

import falcon
import json
import requests
import time
import html
import DBFunctions
import psycopg2
import math
import redis
from pprint import pprint
from inspect import getmembers
from collections import defaultdict
import Submission
import Comment
import User
import Test
import Parameters
from Helpers import *
from configparser import ConfigParser


class Middleware(object):
    def process_request(self, req, resp):
        print ("Process Request")
        #req.context = {}
        #req.context['a'] = {}
        #req.context['a']['b'] = "hello"
        #req['stash'] = "test"
        #setattr(req,"stash",{})
        #print(dir(req))
        #print (vars(req))
        #print(req.remote_addr)
        #print(req.__dict__)
        #print(req.params)
        #req['stash']['a'] = "roger"
        #print(req.stash)
        #for property, value in vars(req).iteritems():
            #print property, ": ", value
        pass

    def process_resource(self, req, resp, resource, params):
        print ("Process Resourse")
        print (req.params)
        if 'q' in req.params:
            print (req.params)
            req.params['q'] = "test123"
            print (req.params)
        pass

    def process_response(self, req, resp, resource):
        #resp.body = json.dumps("{'data':'stuff'}",sort_keys=True,indent=4, separators=(',', ': '))
        #print(resp.body)
        pass


#api = falcon.API(middleware=[Middleware()])
api = falcon.API()
api.add_route('/reddit/search', Comment.search())
api.add_route('/reddit/comment/search', Comment.search())
api.add_route('/reddit/search/comment', Comment.search())
api.add_route('/reddit/search/submission', Submission.search())
api.add_route('/reddit/submission/search', Submission.search())
api.add_route('/reddit/analyze/user/{author}', User.Analyze())
api.add_route('/get/comment_ids/{submission_id}', Submission.getCommentIDs())
api.add_route('/reddit/submission/comment_ids/{submission_id}', Submission.getCommentIDs())
api.add_route('/test', Test.test())

