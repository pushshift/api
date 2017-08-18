import time
import html
from collections import defaultdict
import Parameters
from Helpers import *


class search:
    params = None
    def on_get(self, req, resp):
        start = time.time()
        q = req.get_param('q');
        self.params = req.params
        response = self.search("http://mars:9200/rs/submissions/_search");
        results = []
        data = {}
        for hit in response["data"]["hits"]["hits"]:
            source = hit["_source"]
            source["id"] = base36encode(int(hit["_id"]))

            if 'subreddit_id' in source and source["subreddit_id"] is not None and LooksLikeInt(source["subreddit_id"]):
                source["subreddit_id"] = "t5_" + base36encode(source["subreddit_id"])
            else:
                source["subreddit_id"] = None

            if 'author_flair_text' in source:
                source["author_flair_text"] = html.unescape(source["author_flair_text"])
            else:
                source["author_flair_text"] = None

            if 'author_flair_css_class' in source:
                source["author_flair_css_class"] = html.unescape(source["author_flair_css_class"])
            else:
                source["author_flair_css_class"] = None

            if source["permalink"]:
                source["full_link"] = "https://www.reddit.com" + source["permalink"]

            if 'fields' in self.params:
                if isinstance(self.params['fields'], str):
                    self.params['fields'] = [self.params['fields']]
                self.params['fields'] = [x.lower() for x in self.params['fields']]
                for key in list(source):
                    if key.lower() not in self.params['fields']:
                        source.pop(key, None)

            results.append(source)

        if 'aggregations' in response["data"]:
            data['aggs'] = {}
            if 'subreddit' in response['data']['aggregations']:
                for bucket in response['data']['aggregations']['subreddit']['buckets']:
                    bucket['score'] = round(bucket['doc_count'] / bucket['bg_count'],5)
                newlist = sorted(response['data']['aggregations']['subreddit']['buckets'], key=lambda k: k['score'], reverse=True)
                data['aggs']['subreddit'] = newlist

            if 'author' in response['data']['aggregations']:
                for bucket in response['data']['aggregations']['author']['buckets']:
                    if 'score' in bucket:
                        bucket['score'] = bucket['doc_count'] / bucket['bg_count']
                newlist = response['data']['aggregations']['author']['buckets']
                data['aggs']['author'] = newlist

            if 'created_utc' in response['data']['aggregations']:
                for bucket in response['data']['aggregations']['created_utc']['buckets']:
                    bucket.pop('key_as_string', None)
                    bucket['key'] = int(bucket['key'] / 1000)
                data['aggs']['created_utc'] = response['data']['aggregations']['created_utc']['buckets']

            if 'domain' in response['data']['aggregations']:
                newBuckets = []
                for bucket in response['data']['aggregations']['domain']['buckets']:
                    if 'self.' in bucket['key']:
                        continue
                    else:
                        newBuckets.append(bucket)
                data['aggs']['domain'] = newBuckets

            if 'time_of_day' in response['data']['aggregations']:
                for bucket in response['data']['aggregations']['time_of_day']['buckets']:
                    bucket['bg_percentage'] = round(bucket['bg_count'] * 100 / response['data']['aggregations']['time_of_day']['bg_count'], 5)
                    bucket['doc_percentage'] = round(bucket['doc_count'] * 100 / response['data']['aggregations']['time_of_day']['doc_count'], 5)
                    bucket['deviation_percentage'] = round(bucket['doc_percentage'] - bucket['bg_percentage'],4)
                    bucket['utc_hour'] = bucket['key']
                    bucket.pop('score', None)
                    bucket.pop('key',None)
                newlist = sorted(response['data']['aggregations']['time_of_day']['buckets'], key=lambda k: k['utc_hour'])
                data['aggs']['time_of_day'] = newlist


        end = time.time()
        data['data'] = results;
        data['metadata'] = {}
        data['metadata'] = response['metadata']
        data['metadata'] = self.params
        data['metadata']['execution_time_milliseconds'] = round((end - start) * 1000,2)
        data['metadata']['version'] = 'v3.0'
        data['metadata']['results_returned'] = len(response['data']['hits']['hits'])
        data['metadata']['timed_out'] = response['data']['timed_out']
        data['metadata']['total_results'] = response['data']['hits']['total']
        data['metadata']['shards'] = {}
        data['metadata']['shards'] = response['data']['_shards']
        resp.cache_control = ['public','max-age=2','s-maxage=2']
        resp.body = json.dumps(data,sort_keys=True,indent=4, separators=(',', ': '))

    def search(self, uri):
        nested_dict = lambda: defaultdict(nested_dict)
        q = nested_dict()
        q['query']['bool']['filter'] = []
        q['query']['bool']['must_not'] = []
        self.params, q = Parameters.process(self.params,q)

        if 'q' in self.params and self.params['q'] is not None:
            sqs = nested_dict()
            sqs['simple_query_string']['query'] = self.params['q']
            sqs['simple_query_string']['default_operator'] = 'and'
            q['query']['bool']['filter'].append(sqs)

        conditions = ["title","selftext"]
        for condition in conditions:
            if condition in self.params and self.params[condition] is not None:
                sqs = nested_dict()
                sqs['simple_query_string']['query'] = self.params[condition]
                sqs['simple_query_string']['fields'] = [condition]
                sqs['simple_query_string']['default_operator'] = 'and'
                q['query']['bool']['filter'].append(sqs)

        not_conditions = ["title:not", "q:not", "selftext:not"]
        for condition in not_conditions:
            if condition in self.params and self.params[condition] is not None:
                sqs = nested_dict()
                sqs['simple_query_string']['query'] = self.params[condition]
                if condition != 'q:not':
                    sqs['simple_query_string']['fields'] = [condition.split(":")[0]]
                sqs['simple_query_string']['default_operator'] = 'and'
                q['query']['bool']['must_not'].append(sqs)

        min_doc_count = 0
        if 'min_doc_count' in self.params and self.params['min_doc_count'] is not None and LooksLikeInt(self.params['min_doc_count']):
            min_doc_count = self.params['min_doc_count']

        if 'aggs' in self.params:
            if isinstance(self.params['aggs'], str):
                self.params['aggs'] = [self.params['aggs']]
            for agg in list(self.params['aggs']):
                if agg.lower() == 'subreddit':
                    q['aggs']['subreddit']['significant_terms']['field'] = 'subreddit.keyword'
                    q['aggs']['subreddit']['significant_terms']['size'] = 1000
                    q['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['lang'] = 'painless'
                    q['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['inline'] = 'params._subset_freq'
                    q['aggs']['subreddit']['significant_terms']['min_doc_count'] = min_doc_count

                if agg.lower() == 'author':
                    q['aggs']['author']['terms']['field'] = 'author.keyword'
                    q['aggs']['author']['terms']['size'] = 1000
                    q['aggs']['author']['terms']['order']['_count'] = 'desc'
                    #q['aggs']['author']['significant_terms']['script_heuristic']['script']['lang'] = 'painless'
                    #q['aggs']['author']['significant_terms']['script_heuristic']['script']['inline'] = 'params._subset_freq'
                    #q['aggs']['author']['significant_terms']['min_doc_count'] = min_doc_count

                if agg.lower() == 'created_utc':
                    q['aggs']['created_utc']['date_histogram']['field'] = 'created_utc'
                    if self.params['frequency'] is None:
                        self.params['frequency'] = "day"
                    q['aggs']['created_utc']['date_histogram']['interval'] = self.params['frequency']
                    q['aggs']['created_utc']['date_histogram']['order']['_key'] = 'asc'

                if agg.lower() == 'domain':
                    q['aggs']['domain']['terms']['field'] = 'domain.keyword'
                    q['aggs']['domain']['terms']['size'] = 1000
                    q['aggs']['domain']['terms']['order']['_count'] = 'desc'

                if agg.lower() == 'time_of_day':
                    q['aggs']['time_of_day']['significant_terms']['field'] = 'hour'
                    q['aggs']['time_of_day']['significant_terms']['size'] = 25
                    q['aggs']['time_of_day']['significant_terms']['percentage']

        response = requests.get(uri, data=json.dumps(q))
        results = {}
        results['data'] = json.loads(response.text)
        results['metadata'] = {}
        results['metadata']['sort'] = self.params['sort']
        results['metadata']['sort_type'] = self.params['sort_type']
        return results


class getCommentIDs:

    def on_get(self, req, resp, submission_id):
        submission_id = submission_id.lower()
        if submission_id[:3] == 't3_':
            submission_id = submission_id[3:]
        submission_id = base36decode(submission_id)
        rows = DBFunctions.pgdb.execute("SELECT (json->>'id')::bigint comment_id FROM comment WHERE (json->>'link_id')::int = %s ORDER BY comment_id ASC LIMIT 50000",submission_id)
        results = []
        data = {}
        if rows:
            for row in rows:
                comment_id = row[0]
                results.append(base36encode(comment_id))
        data['data'] = results;
        resp.cache_control = ["public","max-age=5","s-maxage=5"]
        resp.body = json.dumps(data,sort_keys=True,indent=4, separators=(',', ': '))

