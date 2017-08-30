import time
import html
from collections import defaultdict
import Parameters
from Helpers import *


class search:
    def on_get(self, req, resp):
        self.pp = req.context['processed_parameters']
        self.es = req.context['es_query']

        if 'ids' in self.pp:
            data = self.getIds(self.pp['ids'])
            resp.context["data"] = data
            return

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

            if 'fields' in self.pp:
                if isinstance(self.pp['fields'], str):
                    self.pp['fields'] = [self.pp['fields']]
                self.pp['fields'] = [x.lower() for x in self.pp['fields']]
                for key in list(source):
                    if key.lower() not in self.pp['fields']:
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

        data["data"] = results
        data['metadata'] = {}
        data['metadata'] = response['metadata']
        data['metadata'] = self.pp
        data['metadata']['results_returned'] = len(response['data']['hits']['hits'])
        data['metadata']['timed_out'] = response['data']['timed_out']
        data['metadata']['total_results'] = response['data']['hits']['total']
        data['metadata']['shards'] = {}
        data['metadata']['shards'] = response['data']['_shards']
        resp.context['data'] = data

    def search(self, uri):
        nested_dict = lambda: defaultdict(nested_dict)

        if 'q' in self.pp and self.pp['q'] is not None:
            sqs = nested_dict()
            sqs['simple_query_string']['query'] = self.pp['q']
            sqs['simple_query_string']['default_operator'] = 'and'
            self.es['query']['bool']['filter'].append(sqs)

        conditions = ["title","selftext"]
        for condition in conditions:
            if condition in self.pp and self.pp[condition] is not None:
                sqs = nested_dict()
                sqs['simple_query_string']['query'] = self.pp[condition]
                sqs['simple_query_string']['fields'] = [condition]
                sqs['simple_query_string']['default_operator'] = 'and'
                self.es['query']['bool']['filter'].append(sqs)

        not_conditions = ["title:not", "q:not", "selftext:not"]
        for condition in not_conditions:
            if condition in self.pp and self.pp[condition] is not None:
                sqs = nested_dict()
                sqs['simple_query_string']['query'] = self.pp[condition]
                if condition != 'q:not':
                    sqs['simple_query_string']['fields'] = [condition.split(":")[0]]
                sqs['simple_query_string']['default_operator'] = 'and'
                self.es['query']['bool']['must_not'].append(sqs)

        min_doc_count = 0
        if 'min_doc_count' in self.pp and self.pp['min_doc_count'] is not None and LooksLikeInt(self.pp['min_doc_count']):
            min_doc_count = self.pp['min_doc_count']

        if 'aggs' in self.pp:
            if isinstance(self.pp['aggs'], str):
                self.pp['aggs'] = [self.pp['aggs']]
            for agg in list(self.pp['aggs']):
                if agg.lower() == 'subreddit':
                    self.es['aggs']['subreddit']['significant_terms']['field'] = 'subreddit.keyword'
                    self.es['aggs']['subreddit']['significant_terms']['size'] = 1000
                    self.es['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['lang'] = 'painless'
                    self.es['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['inline'] = 'params._subset_freq'
                    self.es['aggs']['subreddit']['significant_terms']['min_doc_count'] = min_doc_count

                if agg.lower() == 'author':
                    self.es['aggs']['author']['terms']['field'] = 'author.keyword'
                    self.es['aggs']['author']['terms']['size'] = 1000
                    self.es['aggs']['author']['terms']['order']['_count'] = 'desc'
                    #self.es['aggs']['author']['significant_terms']['script_heuristic']['script']['lang'] = 'painless'
                    #self.es['aggs']['author']['significant_terms']['script_heuristic']['script']['inline'] = 'params._subset_freq'
                    #self.es['aggs']['author']['significant_terms']['min_doc_count'] = min_doc_count

                if agg.lower() == 'created_utc':
                    self.es['aggs']['created_utc']['date_histogram']['field'] = 'created_utc'
                    if 'frequency' not in self.pp or self.pp['frequency'] is None:
                        self.pp['frequency'] = "day"
                    self.es['aggs']['created_utc']['date_histogram']['interval'] = self.pp['frequency']
                    self.es['aggs']['created_utc']['date_histogram']['order']['_key'] = 'asc'

                if agg.lower() == 'domain':
                    self.es['aggs']['domain']['terms']['field'] = 'domain.keyword'
                    self.es['aggs']['domain']['terms']['size'] = 1000
                    self.es['aggs']['domain']['terms']['order']['_count'] = 'desc'

                if agg.lower() == 'time_of_day':
                    self.es['aggs']['time_of_day']['significant_terms']['field'] = 'hour'
                    self.es['aggs']['time_of_day']['significant_terms']['size'] = 25
                    self.es['aggs']['time_of_day']['significant_terms']['percentage']

        response = requests.get(uri, data=json.dumps(self.es))
        results = {}
        results['data'] = json.loads(response.text)
        results['metadata'] = {}
        results['metadata']['sort'] = self.pp['sort']
        results['metadata']['sort_type'] = self.pp['sort_type']
        return results

    def getIds(self, ids):
        nested_dict = lambda: defaultdict(nested_dict)
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        ids_to_fetch = []
        for id in ids:
            id = id.lower()
            if id[:3] == "t3_":
                id = id[3:]
            ids_to_fetch.append(base36decode(id))
        q = nested_dict()
        self.es["query"]["terms"]["id"] = ids_to_fetch
        self.es["size"] = 500
        response = requests.get("http://mars:9200/rs/submissions/_search", data=json.dumps(q))
        s = json.loads(response.text)
        results = []
        for hit in s["hits"]["hits"]:
            source = hit["_source"]
            base_10_id = source["id"]
            source["id"] = base36encode(int(hit["_id"]))
            if 'subreddit_id' in source:
                source['subreddit_id'] = "t5_" + base36encode(source['subreddit_id'])
            source["full_link"] = "https://www.reddit.com" + source["permalink"]
            if 'fields' in self.pp:
                if isinstance(self.pp['fields'], str):
                    self.pp['fields'] = [self.pp['fields']]
                self.pp['fields'] = [x.lower() for x in self.pp['fields']]
                for key in list(source):
                    if key.lower() not in self.pp['fields']:
                        source.pop(key, None)
            results.append(source)
        data = {}
        data["data"] = results
        data["metadata"] = {}
        return data

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
        data['data'] = results
        resp.context['data'] = data
