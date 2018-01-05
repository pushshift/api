
import time
import html
from collections import defaultdict
import Parameters
from Helpers import *
#import DBFunctions
import falcon

class search:
    def __init__(self,arg=None):
        if arg is not None:
            self.__dict__=arg.__dict__.copy()

    def on_get(self, req, resp):
        self.pp = req.context['processed_parameters']
        self.es = req.context['es_query']
        self.req = req.params
        # What kind of request is this?
        if 'ids' in self.pp:
            data = self.getIds(self.pp['ids'])
        #elif ('q' not in self.pp or self.pp['q'] is None) and ('subreddit' not in self.pp and 'author' not in self.pp):
        #    data = self.getMostRecent(resp)
        else:
            data = self.doElasticSearch()
        resp.context['data'] = data

    def getMostRecent(self,resp):

        # This will need to be optimized eventually to seperate searches with q parameter vs. one without it
        if 'limit' in self.req and self.req['limit'] is not None:
            self.req['limit'] = int(self.req['limit'])
            if self.req['limit'] >= 10000:
                self.pp['size'] = 10000
            else :
                self.pp['size'] = self.req['limit']
        else:
            self.pp['size'] = 100
        resp.context['cache_time'] = 6
        rows = []

        # There is a much better method for doing this but this will suffice for the time being
        link_id_condition = ""
        if 'link_id' in self.pp and self.pp['link_id']:
            link_id_condition = "AND (json->>'link_id')::int IN (" + str(','.join(self.pp['link_id'])) + ") "
        if self.pp['after'] == None:
            self.pp['after'] = 0
        if self.pp['before'] == None:
            self.pp['before'] = 9999999999999
        if not 'subreddit' in self.pp or self.pp['subreddit'] is None:
            rows = DBFunctions.pgdb.execute("SELECT * FROM comment WHERE (json->>'created_utc')::int > %s AND (json->>'created_utc')::int < %s " + link_id_condition + "ORDER BY (json->>'created_utc')::int " + self.pp['sort'] + " LIMIT %s", tuple( (self.pp['after'], self.pp['before'], self.pp['size']) ))
        elif 'subreddit' in self.pp and self.pp['subbreddit'] is not None:
            rows = DBFunctions.pgdb.execute("SELECT * FROM comment WHERE (json->>'created_utc')::int > %s AND (json->>'created_utc')::int < %s " + link_id_condition + "AND lower(json->>'subreddit') = %s ORDER BY (json->>'created_utc')::int " + self.pp['sort'] + " LIMIT %s", tuple( (self.pp['after'], self.pp['before'], self.pp['subreddit'], self.pp['size']) ))
        elif 'author' in self.pp and self.pp['suthor'] is not None:
            rows = DBFunctions.pgdb.execute("SELECT * FROM comment WHERE (json->>'created_utc')::int > %s AND (json->>'created_utc')::int < %s " + link_id_condition + "AND lower(json->>'author') = %s ORDER BY (json->>'created_utc')::int " + self.pp['sort'] + " LIMIT %s", tuple( (self.pp['after'], self.pp['before'], self.pp['author'], self.pp['size']) ))

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
        data['data'] = results
        return data

    def getIds(self,ids):
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        ids_to_get_from_db = []
        for id in ids:
            id = id.lower()
            if id[:3] == 't1_':
                id = id[3:]
            # Having issues with binding and IN statements -- need to resolve.  This will prevent SQL injection for the time being
            bigint = int(base36decode(id))
            ids_to_get_from_db.append(bigint)
        rows = DBFunctions.pgdb.execute("SELECT * FROM comment WHERE (json->>'id')::bigint IN (" + ','.join(map(str, ids_to_get_from_db)) + ") LIMIT 5000",())
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
        data['data'] = results
        return data

    def doElasticSearch(self):

        self.pp['index'] = "rc"

        # Only search the current comment index if after is set and within a month of current time
        if 'after' in self.pp and self.pp['after'] is not None:
            pass

            # This section needs some logic to help limit the number of indexes looked at if we know the time bounds
            # from the supplied before and after parameters
            # ----

        response = self.search("http://localhost:9200/" + self.pp['index'] + "/comment/_search")
        print(response)
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

            if 'distinguished' not in source:
                source["distinguished"] = None

            if 'author_flair_text' in source:
                source["author_flair_text"] = html.unescape(source["author_flair_text"])
            else:
                source["author_flair_text"] = None

            if 'author_flair_css_class' in source:
                source["author_flair_css_class"] = html.unescape(source["author_flair_css_class"])
            else:
                source["author_flair_css_class"] = None

            if 'fields' in self.pp:
                if isinstance(self.pp['fields'], str):
                    self.pp['fields'] = [self.pp['fields']]
                self.pp['fields'] = [x.lower() for x in self.pp['fields']]
                for key in list(source):
                    if key.lower() not in self.pp['fields']:
                        source.pop(key, None)

            results.append(source)

        if 'aggregations' in response["data"]:
            data["aggs"] = {}
            if 'subreddit' in response["data"]["aggregations"]:
                for bucket in response["data"]["aggregations"]["subreddit"]["buckets"]:
                    bucket["score"] = round(((bucket["doc_count"] / bucket["bg_count"]) * 100),5)
                newlist = sorted(response["data"]["aggregations"]["subreddit"]["buckets"], key=lambda k: k['score'], reverse=True)
                data["aggs"]["subreddit"] = newlist

            if 'author' in response["data"]["aggregations"]:
                for bucket in response["data"]["aggregations"]["author"]["buckets"]:
                    if 'score' in bucket:
                        bucket["score"] = bucket["doc_count"] / bucket["bg_count"]
                newlist = response["data"]["aggregations"]["author"]["buckets"]
                data["aggs"]["author"] = newlist

            for k in ["author_flair_text","author_flair_css_class","utc_hour","day_of_week"]:
                if k in response["data"]["aggregations"]:
                    for bucket in response["data"]["aggregations"][k]["buckets"]:
                        bucket.pop('key_as_string', None)
                    data["aggs"][k] = response["data"]["aggregations"][k]["buckets"]

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
                if "after" in self.pp and self.pp['after'] is not None:
                    after = int(self.pp["after"])
                for item in response["data"]["aggregations"]["link_id"]["buckets"]:
                    if item["key"] in submission_data and submission_data[item["key"]]["created_utc"] > after:
                        print("Got here")
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

        if 'q' in self.pp and self.pp['q'] is not None:
            sqs = nested_dict()
            sqs['simple_query_string']['query'] = self.pp['q']
            sqs['simple_query_string']['fields'] = ['body']
            sqs['simple_query_string']['default_operator'] = 'and'
            self.es['query']['bool']['filter']['bool']['must'].append(sqs)

        min_doc_count = 0
        if 'min_doc_count' in self.pp and self.pp['min_doc_count'] is not None and LooksLikeInt(self.pp['min_doc_count']):
            min_doc_count = self.pp['min_doc_count']

        if 'aggs' in self.pp:
            self.pp['aggs'] = falcon.uri.decode(self.pp['aggs'])
            if isinstance(self.pp['aggs'], str):
                self.pp['aggs'] = self.pp['aggs'].split(",")
            #if isinstance(self.pp['aggs'], str):
            #    self.pp['aggs'] = [self.pp['aggs']]
            for agg in list(self.pp['aggs']):
                if agg.lower() == 'subreddit':
                    self.es['aggs']['subreddit']['significant_terms']['field'] = "subreddit"
                    self.es['aggs']['subreddit']['significant_terms']['size'] = 250
                    self.es['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['lang'] = "painless"
                    self.es['aggs']['subreddit']['significant_terms']['script_heuristic']['script']['inline'] = "params._subset_freq"
                    self.es['aggs']['subreddit']['significant_terms']['min_doc_count'] = min_doc_count

                for k in ["author_flair_text","author_flair_css_class"]:
                    if agg.lower() == k:
                        self.es['aggs'][k]['terms']['field'] = k
                        self.es['aggs'][k]['terms']['size'] = 250
                        self.es['aggs'][k]['terms']['order']['_count'] = 'desc'

                if agg.lower() == 'author':
                    self.es['aggs']['author']['terms']['field'] = 'author'
                    self.es['aggs']['author']['terms']['size'] = 500
                    self.es['aggs']['author']['terms']['order']['_count'] = 'desc'


                if agg.lower() == 'utc_hour':
                    self.es['aggs']['utc_hour']['terms']['field'] = 'utc_hour'
                    self.es['aggs']['utc_hour']['terms']['size'] = 24
                    self.es['aggs']['utc_hour']['terms']['order']['_key'] = 'asc'

                if agg.lower() == 'day_of_week':
                    self.es['aggs']['day_of_week']['terms']['field'] = 'day_of_week'
                    self.es['aggs']['day_of_week']['terms']['size'] = 24
                    self.es['aggs']['day_of_week']['terms']['order']['_key'] = 'asc'

                if agg.lower() == 'created_utc':
                    self.es['aggs']['created_utc']['date_histogram']['field'] = "created_utc"
                    if 'frequency' not in self.pp or self.pp['frequency'] is None:
                        self.pp['frequency'] = "day"
                    self.es['aggs']['created_utc']['date_histogram']['interval'] = self.pp['frequency']
                    self.es['aggs']['created_utc']['date_histogram']['order']['_key'] = "asc"

                if agg.lower() == 'link_id':
                    self.es['aggs']['link_id']['terms']['field'] = "link_id"
                    self.es['aggs']['link_id']['terms']['size'] = 100
                    self.es['aggs']['link_id']['terms']['order']['_count'] = "desc"

        response = None
        try:
            print(json.dumps(self.es))
            response = requests.get(uri, data=json.dumps(self.es), headers={'Content-Type': 'application/json'})
        except requests.exceptions.RequestException as e:
            response = requests.get("http://localhost:9200/rc/comments/_search", data=json.dumps(self.es))

        results = {}
        results['data'] = json.loads(response.text)
        results['metadata'] = {}
        results['metadata'] = self.pp
        results['metadata']['size'] = self.pp['size']
        results['metadata']['sort'] = self.pp['sort']
        results['metadata']['sort_type'] = self.pp['sort_type']
        if 'after' in self.pp and self.pp['after'] is not None:
            results['metadata']['after'] = self.pp['after']
        return results
