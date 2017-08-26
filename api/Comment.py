import time
import html
from collections import defaultdict
import Parameters
from Helpers import *
import DBFunctions

class search:
    params = None
    def on_get(self, req, resp):
        start = time.time()
        #q = req.get_param('q');
        self.params = req.params
        nested_dict = lambda: defaultdict(nested_dict)
        self.q = nested_dict()
        self.params, self.q = Parameters.process(self.params,self.q)
        if 'ids' in self.params:
            data = self.getIds(self.params['ids'])
        else:
            data = self.doElasticSearch()
        end = time.time()
        data["metadata"]["execution_time_milliseconds"] = round((end - start) * 1000,2)
        data["metadata"]["version"] = "v3.0"
        resp.cache_control = ["public","max-age=2","s-maxage=2"]
        resp.body = json.dumps(data,sort_keys=True,indent=4, separators=(',', ': '))

    def getIds(self,ids):
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        ids_to_get_from_db = []
        for id in ids:
            id = id.lower()
            if id[:3] == "t1_":
                id = id[3:]
            ids_to_get_from_db.append(base36decode(id))
        rows = DBFunctions.pgdb.execute("SELECT * FROM comment WHERE (json->>'id')::bigint IN %s LIMIT 5000",tuple(ids_to_get_from_db))
        results = []
        data = {}
        if rows:
            for row in rows:
                comment = row[0]
                comment['id'] = base36encode(comment['id'])
                if 'parent_id' not in comment or comment['parent_id'] == None:
                    comment['parent_id'] = "t3_" + base36encode(comment['link_id'])
                elif comment['parent_id'] == comment['link_id']:
                    comment['parent_id'] = "t3_" + base36encode(comment['link_id'])
                else:
                    comment['parent_id'] = "t1_" + base36encode(comment['parent_id'])
                if 'subreddit_id' in comment:
                    comment['subreddit_id'] = "t5_" + base36encode(comment['subreddit_id'])
                comment['link_id'] = "t3_" + base36encode(comment['link_id'])
                comment.pop('name', None)
                results.append(comment)
        data["data"] = results
        data["metadata"] = {}
        return data

    def doElasticSearch(self):

        self.params['index'] = "rc"
        if 'delta_only' in self.params and self.params['delta_only'] is True:
            self.params['index'] = "rc_delta"
        response = self.search("http://mars:9200/" + self.params['index'] + "/comments/_search")
        results = []
        data = {}
        for hit in response["data"]["hits"]["hits"]:
            source = hit["_source"]
            source["id"] = base36encode(int(hit["_id"]))
            source["link_id"] = "t3_" + base36encode(source["link_id"])

            if 'parent_id' in source:
                source["parent_id"] = "t1_" + base36encode(source["parent_id"])
            else:
                source["parent_id"] = source["link_id"]

            source["subreddit_id"] = "t5_" + base36encode(source["subreddit_id"])

            if 'author_flair_text' in source:
                source["author_flair_text"] = html.unescape(source["author_flair_text"])
            else:
                source["author_flair_text"] = None

            if 'author_flair_css_class' in source:
                source["author_flair_css_class"] = html.unescape(source["author_flair_css_class"])
            else:
                source["author_flair_css_class"] = None

            if 'fields' in self.params:
                if isinstance(self.params['fields'], str):
                    self.params['fields'] = [self.params['fields']]
                self.params['fields'] = [x.lower() for x in self.params['fields']]
                for key in list(source):
                    if key.lower() not in self.params['fields']:
                        source.pop(key, None)

            results.append(source)

        if 'aggregations' in response["data"]:
            data["aggs"] = {}
            if 'subreddit' in response["data"]["aggregations"]:
                for bucket in response["data"]["aggregations"]["subreddit"]["buckets"]:
                    bucket["score"] = bucket["doc_count"] / bucket["bg_count"]
                newlist = sorted(response["data"]["aggregations"]["subreddit"]["buckets"], key=lambda k: k['score'], reverse=True)
                data["aggs"]["subreddit"] = newlist

            if 'author' in response["data"]["aggregations"]:
                for bucket in response["data"]["aggregations"]["author"]["buckets"]:
                    if 'score' in bucket:
                        bucket["score"] = bucket["doc_count"] / bucket["bg_count"]
                newlist = response["data"]["aggregations"]["author"]["buckets"]
                data["aggs"]["author"] = newlist

            if 'created_utc' in response["data"]["aggregations"]:
                for bucket in response["data"]["aggregations"]["created_utc"]["buckets"]:
                    bucket.pop('key_as_string', None)
                    bucket["key"] = int(bucket["key"] / 1000)
                data["aggs"]["created_utc"] = response["data"]["aggregations"]["created_utc"]["buckets"]

            if 'link_id' in response["data"]["aggregations"]:
                ids = []
                for bucket in response["data"]["aggregations"]["link_id"]["buckets"]:
                    if 'score' in bucket:
                        bucket["score"] = bucket["doc_count"] / bucket["bg_count"]
                    ids.append(bucket["key"])
                submission_data = getSubmissionsFromES(ids)
                newlist = []
                after = 0
                if "after" in self.params and self.params['after'] is not None:
                    after = int(self.params["after"])
                for item in response["data"]["aggregations"]["link_id"]["buckets"]:
                    if item["key"] in submission_data and submission_data[item["key"]]["created_utc"] > after:
                        item["data"] = submission_data[item["key"]]
                        item["data"]["full_link"] = "https://www.reddit.com" + item["data"]["permalink"]
                        newlist.append(item)
                data["aggs"]["link_id"] = newlist

        data["data"] = results
        data["metadata"] = {}
        data["metadata"] = response["metadata"]
        data["metadata"]["results_returned"] = len(response["data"]["hits"]["hits"])
        data["metadata"]["timed_out"] = response["data"]["timed_out"]
        data["metadata"]["total_results"] = response["data"]["hits"]["total"]
        data["metadata"]["shards"] = {}
        data["metadata"]["shards"] = response["data"]["_shards"]
        return data

    def search(self, uri):
        nested_dict = lambda: defaultdict(nested_dict)
        #q = nested_dict()
        self.q['query']['bool']['filter'] = []

        if 'q' in self.params and self.params['q'] is not None:
            sqs = nested_dict()
            sqs['simple_query_string']['query'] = self.params['q']
            sqs['simple_query_string']['fields'] = ['body']
            sqs['simple_query_string']['default_operator'] = 'and'
            self.q['query']['bool']['filter'].append(sqs)

        #self.params, q = Parameters.process(self.params,q)

        min_doc_count = 0
        if 'min_doc_count' in self.params and self.params['min_doc_count'] is not None and LooksLikeInt(self.params['min_doc_count']):
            min_doc_count = params['min_doc_count']

        if 'aggs' in self.params:
            if isinstance(self.params['aggs'], str):
                self.params['aggs'] = [self.params['aggs']]
            for agg in list(self.params['aggs']):
                if agg.lower() == 'subreddit':
                    q['aggs']['subreddit']['significant_terms']['field'] = "subreddit.keyword"
                    q['aggs']['subreddit']['significant_terms']['size'] = 1000
                    q['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['lang'] = "painless"
                    q['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['inline'] = "params._subset_freq"
                    q['aggs']['subreddit']['significant_terms']['min_doc_count'] = min_doc_count

                if agg.lower() == 'author':
                    q['aggs']['author']['terms']['field'] = 'author.keyword'
                    q['aggs']['author']['terms']['size'] = 1000
                    q['aggs']['author']['terms']['order']['_count'] = 'desc'

                if agg.lower() == 'created_utc':
                    q['aggs']['created_utc']['date_histogram']['field'] = "created_utc"
                    if self.params['frequency'] is None:
                        self.params['frequency'] = "day"
                    q['aggs']['created_utc']['date_histogram']['interval'] = self.params['frequency']
                    q['aggs']['created_utc']['date_histogram']['order']['_key'] = "asc"

                if agg.lower() == 'link_id':
                    q['aggs']['link_id']['terms']['field'] = "link_id"
                    q['aggs']['link_id']['terms']['size'] = 250
                    q['aggs']['link_id']['terms']['order']['_count'] = "desc"

        response = None
        try:
            response = requests.get(uri, data=json.dumps(self.q))
        except requests.exceptions.RequestException as e:
            response = requests.get("http://jupiter:9200/rc/comments/_search", data=json.dumps(self.q))

        results = {}
        results['data'] = json.loads(response.text)
        results['metadata'] = {}
        results['metadata'] = self.params
        results['metadata']['size'] = self.params['size']
        results['metadata']['sort'] = self.params['sort']
        results['metadata']['sort_type'] = self.params['sort_type']
        if 'after' in self.params and self.params['after'] is not None:
            results['metadata']['after'] = self.params['after']
        return results


