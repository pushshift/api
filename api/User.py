import time
import html
from collections import defaultdict
import Parameters
from Helpers import *


class Analyze:
    def on_get(self, req, resp, author):
        start = time.time()
        params = req.params
        searchURL = 'http://mars:9200/rc/comments/_search'
        nested_dict = lambda: defaultdict(nested_dict)
        q = nested_dict()
        size = 2500
        sort_direction = 'desc'
        q['query']['bool']['filter'] = []
        q['size'] = size

        if author is not None:
            terms = nested_dict()
            terms['terms']['author'] =  [author.lower()]
            q['query']['bool']['filter'].append(terms)

        q['size'] = size
        q['sort']['created_utc'] = sort_direction

        q['aggs']['created_utc']['date_histogram']['field'] = 'created_utc'
        q['aggs']['created_utc']['date_histogram']['interval'] = "day"
        q['aggs']['created_utc']['date_histogram']['order']['_key'] = 'asc'

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



