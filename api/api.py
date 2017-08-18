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
import Parameters
from Helpers import *
from configparser import ConfigParser

class AnalyzeUser:
    def on_get(self, req, resp):
        start = time.time()
        params = req.params
        searchURL = 'http://mars:9200/rc/comments/_search'
        nested_dict = lambda: defaultdict(nested_dict)
        q = nested_dict()
        size = 25
        sort_direction = 'desc'
        q['query']['bool']['filter'] = []

        if 'limit' in params:
            params['size'] = params['limit']

        if 'size' in params and params['size'] is not None and LooksLikeInt(params['size']):
            size = 500 if int(params['size']) > 500 else int(params['size'])
            q['size'] = size
        else:
            q['size'] = 25

        if 'author' in params and params['author'] is not None:
            terms = nested_dict()
            terms['terms']['author'] =  [params['author'].lower()]
            q['query']['bool']['filter'].append(terms)

        q['size'] = size
        q['sort']['score'] = sort_direction

        q['aggs']['subreddit']['terms']['field'] = 'subreddit.keyword'
        q['aggs']['subreddit']['terms']['size'] = size
        q['aggs']['subreddit']['terms']['order']['_count'] = 'desc'

        q['aggs']['link_id']['terms']['field'] = 'link_id'
        q['aggs']['link_id']['terms']['size'] = 25
        q['aggs']['link_id']['terms']['order']['_count'] = 'desc'

        request = requests.get(searchURL, data=json.dumps(q))
        response = json.loads(request.text)

        if response.get('aggregations', {}).get('link_id', {}).get('buckets',{}):
            for row in response['aggregations']['link_id']['buckets']:
                row['key'] = 't3_' + base36encode(row['key'])

        end = time.time()
        data = {}
        data['data'] = response
        data['metadata'] = {}
        data['metadata']['execution_time_milliseconds'] = round((end - start) * 1000,2)
        data['metadata']['version'] = 'v3.0'
        resp.cache_control = ['public','max-age=2','s-maxage=2']
        resp.body = json.dumps(data,sort_keys=True,indent=4, separators=(',', ': '))

class getCommentsForSubmission:

    def on_get(self, req, resp, submission_id):
        submission_id = submission_id.lower()
        if submission_id[:3] == 't3_':
            submission_id = submission_id[3:]
        submission_id = base36decode(submission_id)
        rows = pgdb.execute("SELECT (json->>'id')::bigint comment_id FROM comment WHERE (json->>'link_id')::int = %s ORDER BY comment_id ASC LIMIT 50000",submission_id)
        results = []
        data = {}
        if rows:
            for row in rows:
                comment_id = row[0]
                results.append(base36encode(comment_id))
        data['data'] = results;
        resp.cache_control = ["public","max-age=5","s-maxage=5"]
        resp.body = json.dumps(data,sort_keys=True,indent=4, separators=(',', ': '))

def database_connection():
    connection = psycopg2.connect("dbname='reddit' user='" + DB_USER + "' host='jupiter' password='" + DB_PASSWORD + "'")
    return connection

config = ConfigParser()
config.read ('credentials.ini')
DB_PASSWORD = config.get('database','password')
DB_USER = config.get('database','user')
pgdb = DBFunctions.pgdb()
r = redis.StrictRedis(host='localhost', port=6379, db=1)
api = falcon.API()
api.add_route('/reddit/search', Comment.search())
api.add_route('/reddit/comment/search', Comment.search())
api.add_route('/reddit/search/comment', Comment.search())
api.add_route('/reddit/search/submission', Submission.search())
api.add_route('/reddit/submission/search', Submission.search())
api.add_route('/reddit/analyze/user', AnalyzeUser())
api.add_route('/get/comment_ids/{submission_id}', getCommentsForSubmission())
