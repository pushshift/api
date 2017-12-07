import time
import html
from collections import defaultdict
from operator import itemgetter
import Parameters
from Helpers import *
import Comment
import math

class search:
    def on_get(self, req, resp):
        self.pp = req.context['processed_parameters']
        self.es = req.context['es_query']

        # Handle Cache for expensive requests (this will need to be organized better later on)
        if 'advanced' in self.pp and self.pp['advanced'].lower() == "true":
            resp.context["cache_time"] = 60

        if 'ids' in self.pp:
            data = self.getIds(self.pp['ids'])
            resp.context["data"] = data
            return

        response = self.search("http://localhost:9200/rs/submission/_search");
        #print(response)
        hits = {}
        data = {}
        order = 0;
        for hit in response["data"]["hits"]["hits"]:
            source = hit["_source"]
            source["id"] = base36encode(int(hit["_id"]))
            order += 1
            source["order"] = order
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
            hits[int(hit["_id"])] = source

        if 'aggregations' in response["data"]:
            data['aggs'] = {}

            if 'subreddit' in response['data']['aggregations']:
                newSubBuckets = []
                for bucket in response['data']['aggregations']['subreddit']['buckets']:
                    #bucket["score"] = round(((bucket["doc_count"] / bucket["bg_count"]) * 100),5)
                #newlist = sorted(response["data"]["aggregations"]["subreddit"]["buckets"], key=lambda k: k['doc_count'], reverse=True)
                    newSubBuckets.append(bucket)
                data['aggs']['subreddit'] = newSubBuckets

            if 'author' in response['data']['aggregations']:
                for bucket in response['data']['aggregations']['author']['buckets']:
                    if 'score' in bucket:
                        bucket['score'] = bucket['doc_count'] / bucket['bg_count']
                newlist = response['data']['aggregations']['author']['buckets']
                data['aggs']['author'] = newlist

            for k in ["author_flair_text","author_flair_css_class","link_flair_text","link_flair_css_class","url"]:
                if k in response["data"]["aggregations"]:
                    for bucket in response["data"]["aggregations"][k]["buckets"]:
                        bucket.pop('key_as_string', None)
                    data["aggs"][k] = response["data"]["aggregations"][k]["buckets"]

            if 'created_utc' in response['data']['aggregations']:
                for bucket in response['data']['aggregations']['created_utc']['buckets']:
                    bucket.pop('key_as_string', None)
                    bucket['key'] = int(bucket['key'] / 1000)
                data['aggs']['created_utc'] = response['data']['aggregations']['created_utc']['buckets']

            if 'comment_created_utc' in response['data']['aggregations']:
                for bucket in response['data']['aggregations']['comment_created_utc']['buckets']:
                    bucket.pop('key_as_string', None)
                    bucket['key'] = int(bucket['key'])
                data['aggs']['comment_created_utc'] = response['data']['aggregations']['comment_created_utc']['buckets']

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

            if 'link_id' in response["data"]["aggregations"]:
                ids = []
                for bucket in response["data"]["aggregations"]["link_id"]["buckets"]:
                    if int(bucket["key"]) in hits:
                        continue
                    if 'score' in bucket:
                        bucket["score"] = bucket["doc_count"] / bucket["bg_count"]
                    ids.append(bucket["key"])
                submission_data = getSubmissionsFromES(ids)
                newlist = []
                after = 0
                if "after" in self.pp and self.pp['after'] is not None:
                    after = int(self.pp["after"])
                for item in response["data"]["aggregations"]["link_id"]["buckets"]:
                    if item["key"] in submission_data and submission_data[item["key"]]["created_utc"] > after:
                        item["data"] = submission_data[item["key"]]
                        item["data"]["full_link"] = "https://www.reddit.com" + item["data"]["permalink"]
                        newlist.append(item)
                data["aggs"]["link_id"] = newlist

        results = list(sorted(hits.values(), key=itemgetter('order')))
        for result in results: result.pop('order',None)
        data["data"] = results
        data['metadata'] = {}
        data['metadata'] = response['metadata']
        data['metadata'] = self.pp
        data['metadata']['results_returned'] = len(response['data']['hits']['hits'])
        data['metadata']['timed_out'] = response['data']['timed_out']
        data['metadata']['total_results'] = response['data']['hits']['total']
        if 'filter' in self.pp:
            data['metadata']['filter'] = self.pp['filter']
        data['metadata']['shards'] = {}
        data['metadata']['shards'] = response['data']['_shards']
        resp.context['data'] = data

    def search(self, uri):
        nested_dict = lambda: defaultdict(nested_dict)

        if 'q' in self.pp and self.pp['q'] is not None:
            sqs = nested_dict()
            sqs['simple_query_string']['query'] = self.pp['q']
            sqs['simple_query_string']['fields'] = ["title^5","selftext^2"]
            sqs['simple_query_string']['default_operator'] = 'and'
            self.es['query']['bool']['filter']['bool']['must'].append(sqs)

        conditions = ["title","selftext"]
        for condition in conditions:
            if condition in self.pp and self.pp[condition] is not None:
                sqs = nested_dict()
                sqs['simple_query_string']['query'] = self.pp[condition]
                sqs['simple_query_string']['fields'] = [condition]
                sqs['simple_query_string']['default_operator'] = 'and'
                self.es['query']['bool']['filter']['bool']['must'].append(sqs)

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
                    self.es['aggs']['subreddit']['terms']['field'] = 'subreddit'
                    self.es['aggs']['subreddit']['terms']['size'] = 100
                    self.es['aggs']['subreddit']['terms']['order']['_count'] = 'desc'

                    #self.es['aggs']['subreddit']['significant_terms']['field'] = 'subreddit.keyword'
                    #self.es['aggs']['subreddit']['significant_terms']['size'] = 1000
                    #self.es['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['lang'] = 'painless'
                    #self.es['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['inline'] = 'params._subset_freq'
                    #self.es['aggs']['subreddit']['significant_terms']['min_doc_count'] = min_doc_count


                for k in ["author_flair_text","author_flair_css_class","link_flair_text","link_flair_css_class"]:
                    if agg.lower() == k:
                        self.es['aggs'][k]['terms']['field'] = k
                        self.es['aggs'][k]['terms']['size'] = 250
                        self.es['aggs'][k]['terms']['order']['_count'] = 'desc'

                if agg.lower() == 'url':
                    self.es['aggs']['url']['terms']['field'] = 'url.keyword'
                    self.es['aggs']['url']['terms']['size'] = 100
                    self.es['aggs']['url']['terms']['order']['_count'] = 'desc'

                if agg.lower() == 'author':
                    self.es['aggs']['author']['terms']['field'] = 'author.keyword'
                    self.es['aggs']['author']['terms']['size'] = 100
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
                    self.es['aggs']['domain']['terms']['size'] = 250
                    self.es['aggs']['domain']['terms']['order']['_count'] = 'desc'

                if agg.lower() == 'time_of_day':
                    self.es['aggs']['time_of_day']['significant_terms']['field'] = 'hour'
                    self.es['aggs']['time_of_day']['significant_terms']['size'] = 25
                    self.es['aggs']['time_of_day']['significant_terms']['percentage']

        routing = None
        if 'subreddit' in self.pp:
            routing = {'routing':','.join(self.pp['subreddit'])}
        response = requests.get(uri, data=json.dumps(self.es),headers={'Content-Type': 'application/json'},params=routing)
        r = json.loads(response.text)
        if 'advanced' in self.pp and self.pp['advanced'].lower() == "true":
            #resp.context['cache_time'] = 60
            self.es['size'] = 0
            self.es.pop('sort',None)
            self.es['aggs'] = nested_dict()

            # Remove Domain from ES object if present
            for key in self.es['query']['bool']['filter']['bool']['must']:
                if 'terms' in key and 'domain' in key['terms']:
                    self.es['query']['bool']['filter']['bool']['must'].remove(key)
                if 'range' in key and 'num_comments' in key['range']:
                    self.es['query']['bool']['filter']['bool']['must'].remove(key)

            if 'aggs' not in self.pp:
                self.pp['aggs'] = []
            self.pp['aggs'].append('link_id')
            self.pp['aggs'].append('created_utc')
            c = Comment.search(self)
            cr = c.doElasticSearch()
            cd = cr['aggs']['link_id']
            comment_created_utc_agg = cr['aggs']['created_utc']
            if 'aggregations' not in r:
                r['aggregations'] = {}
            if 'link_id' not in r['aggregations']:
                r['aggregations']['link_id'] = {}
            r['aggregations']['comment_created_utc'] = {}
            r['aggregations']['link_id']['buckets'] = cd
            r['aggregations']['comment_created_utc']['buckets'] = comment_created_utc_agg
        results = {}
        results['data'] = r
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
        q["query"]["ids"]["values"] = ids_to_fetch
        response = requests.get("http://localhost:9200/rs/submission/_search", data=json.dumps(q))
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
        #rows = DBFunctions.pgdb.execute("SELECT (json->>'id')::bigint comment_id FROM comment WHERE (json->>'link_id')::int = %s ORDER BY comment_id ASC LIMIT 50000",submission_id)
        results = []
        data = {}
        if rows:
            for row in rows:
                comment_id = row[0]
                results.append(base36encode(comment_id))
        data['data'] = results
        resp.context['data'] = data

class timeLine:

    def on_get(self, req, resp, submission_id):
        submission_id = submission_id.lower()
        if submission_id[:3] == 't3_':
            submission_id = submission_id[3:]
        submission_id = base36decode(submission_id)
        rows = DBFunctions.pgdb.execute("SELECT (json->>'created_utc')::int created_utc FROM comment WHERE (json->>'link_id')::int = %s ORDER BY (json->>'created_utc')::int ASC LIMIT 100000",submission_id)
        results = []
        data = {}
        row_data = {}
        if rows:
            for row in rows:
                created_utc = math.floor(int(row[0])/60)*60
                if created_utc in row_data:
                    row_data[created_utc] += 1
                else:
                    row_data[created_utc] = 1
        data['data'] = sorted(row_data.items(), key=itemgetter(0))
        resp.context['data'] = data

