from collections import defaultdict
import requests
import json
import DBFunctions


def LooksLikeInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def base36encode(number, alphabet='0123456789abcdefghijklmnopqrstuvwxyz'):
    """Converts an integer to a base36 string."""
    if not isinstance(number, (int, int)):
        raise TypeError('number must be an integer')

    base36 = ''
    sign = ''

    if number < 0:
        sign = '-'
        number = -number

    if 0 <= number < len(alphabet):
        return sign + alphabet[number]

    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36

    return sign + base36


def base36decode(number):
    return int(number, 36)


def getSubmissionsFromES(ids):
    nested_dict = lambda: defaultdict(nested_dict)
    if not isinstance(ids, (list, tuple)):
        ids = [ids]
    ids_to_get = []
    q = nested_dict()
    q["query"]["terms"]["id"] = ids
    q["size"] = 1000
    response = requests.get("http://mars:9200/rs/submissions/_search", data=json.dumps(q))
    s = json.loads(response.text)
    results = {}
    for hit in s["hits"]["hits"]:
        source = hit["_source"]
        base_10_id = source["id"]
        source["id"] = base36encode(int(hit["_id"]))
        results[base_10_id] = source
    return results


def getSubmissionsFromPg(ids):
    if not isinstance(ids, (list, tuple)):
        ids = [ids]
    ids_to_get_from_db = []
    rows = DBFunctions.pgdb.execute("SELECT * FROM submission WHERE (json->>'id')::int IN %s LIMIT 5000", tuple(ids))
    results = {}
    data = {}
    if rows:
        for row in rows:
            submission = row[0]
            base_10_id = submission['id']
            submission['id'] = base36encode(submission['id'])
            if 'subreddit_id' in submission:
                submission['subreddit_id'] = "t5_" + base36encode(submission['subreddit_id'])
            submission.pop('name', None)
            results[base_10_id] = submission
    return results
