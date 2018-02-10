#!/usr/bin/env python3

import falcon
import json
import requests
import time
import html
#import DBFunctions
import psycopg2
import math
import redis
from pprint import pprint
from inspect import getmembers
from collections import defaultdict
import Submission
import Comment
import Subreddit
import User
import Test
import Parameters
from Helpers import *
from configparser import ConfigParser

API_VERSION = "3.0"

class PreProcessing:
    def process_resource(self, req, resp, resource, params):

        # Record start time of request
        req.context["start_time"] = time.time()     # req.context and resp.context (dicts) can be used to stash data

        # Process Parameters
        req.context['processed_parameters'], req.context['es_query'] = Parameters.process(req.params)

class CreateReply:
    def process_response(self, req, resp, resource, req_succeeded):

        if resource is None:
            return
        # Set appropriate cache level for response
        if 'cache_time' in resp.context and resp.context['cache_time'] is not None:
            resp.cache_control = ['public','max-age=' + str(resp.context['cache_time']),'s-maxage=' + str(resp.context['cache_time'])]
        else:
            resp.cache_control = ['public','max-age=1','s-maxage=1']

        # Calculate total execution time for request
        if hasattr(req, 'context') and 'start_time' in req.context:
            execution_time = time.time() - req.context['start_time']

        # Filter out fields if filter parameter is present
        if 'filter' in req.context['processed_parameters']:
            new_list = []
            if isinstance(req.context['processed_parameters']['filter'], str):
                req.context['processed_parameters']['filter'] = [req.context['processed_parameters']['filter']]
            for datum in resp.context['data']['data']:
                new_element = {}
                for filter in req.context['processed_parameters']['filter']:
                    if filter in datum:
                        new_element[filter] = datum[filter]
                new_list.append(new_element)
            resp.context['data']['data'] = new_list

        # Filter out users who requested to be removed from API
        if 'data' in resp.context:
            for datum in resp.context['data']['data']:
                if 'author' in datum:
                    if datum['author'] == "bilbo-t-baggins":
                        resp.context['data']['data'].remove(datum)

        # Create Response and metadata

        # Check if the ensure_ascii paramater was passed (True means that the response will encode non-ascii characters with \uxxxx
        ensure_ascii = False
        if 'ensure_ascii' in req.context['processed_parameters']:
            if req.context['processed_parameters']['ensure_ascii'].lower() == "true": ensure_ascii = True

        if 'data' in resp.context:
            if 'metadata' not in resp.context['data']:
                resp.context['data']['metadata'] = {}

        if 'metadata' in req.context['processed_parameters']:
            resp.context['data']['metadata'].update(req.context['processed_parameters'])
            resp.context['data']['metadata']['metadata'] = True
            resp.context['data']['metadata']['execution_time_milliseconds'] = round((execution_time) * 1000,2)
            resp.context['data']['metadata']['api_version'] = API_VERSION
        else:
            resp.context['data'].pop('metadata',None)

        if 'pretty' in req.context['processed_parameters']:
            if 'metadata' in resp.context['data']: resp.context['data']['metadata']['pretty'] = True
            resp.body = json.dumps(resp.context['data'],sort_keys=True,indent=4, separators=(',', ': '),ensure_ascii=ensure_ascii)
        else:
            resp.body = json.dumps(resp.context['data'],ensure_ascii=ensure_ascii)

class Middleware(object):
    def process_request(self, req, resp):
        #print ('Process Request')
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
        #print ("Process Resourse")
        #print (req.params)
        if 'q' in req.params:
            print (req.params)
            req.params['q'] = "test123"
            print (req.params)
        pass

    def process_response(self, req, resp, resource):
        #resp.body = json.dumps("{'data':'stuff'}",sort_keys=True,indent=4, separators=(',', ': '))
        #print(resp.body)
        pass

api = falcon.API(middleware=[PreProcessing(),CreateReply()])
api.req_options.keep_blank_qs_values = True
api.add_route('/reddit/subreddit/search', Subreddit.search())
api.add_route('/reddit/search/subreddit', Subreddit.search())
api.add_route('/reddit/search', Comment.search())
api.add_route('/reddit/comment/search', Comment.search())
api.add_route('/reddit/search/comment', Comment.search())
api.add_route('/reddit/search/submission', Submission.search())
api.add_route('/reddit/submission/search', Submission.search())
api.add_route('/reddit/analyze/user/{author}', User.Analyze())
api.add_route('/reddit/get/comment_ids/{submission_id}', Submission.getCommentIDs())
api.add_route('/reddit/submission/comment_ids/{submission_id}', Submission.getCommentIDs())
api.add_route('/reddit/submission/comment_ids/{submission_id}', Submission.getCommentIDs())
#api.add_route('/reddit/submission/timeline/{submission_id}', Submission.timeLine())
api.add_route('/test', Test.test())
#api.add_route('/',Test.test())

