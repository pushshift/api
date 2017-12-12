from collections import defaultdict
from Helpers import *
from falcon import uri
import requests
import json
import time
from pprint import pprint

def process(params):
    nested_dict = lambda: defaultdict(nested_dict)
    q = nested_dict()
    q['query']['bool']['filter']['bool']['must'] = []
    q['query']['bool']['filter']['bool']['should'] = []
    q['query']['bool']['must_not'] = []
    params = {k.lower(): v for k, v in params.items()} # Lowercase all parameter names passed
    suggested_sort = "desc";

    if 'link_id' in params and params['link_id'] is not None:
        params['link_id'] = params['link_id'].lower()
        if params['link_id'][:3] == "t3_":
            params['link_id'] = params['link_id'][3:]
        params['link_id'] = str(int(params['link_id'],36))

    conditions = ["subreddit","author","domain","link_id","subreddit_type","user_removed","mod_removed","url","link_flair_text","link_flair_css_class"]
    for condition in conditions:
        if condition in params and params[condition] is not None:
            params[condition] = uri.decode(params[condition])
            if not isinstance(params[condition], (list, tuple)):
                params[condition] = params[condition].split(",")
            param_values = [x.lower() for x in params[condition]]
            # Need to make this a function for when users request to be removed from API
            print(condition)
            if condition == "author":
                while 'bilbo-t-baggins' in param_values: param_values.remove('bilbo-t-baggins')
            terms = nested_dict()
            if params[condition][0][0] == "!":
                terms['terms'][condition] = list(map(lambda x:x.replace("!",""),param_values))
                q['query']['bool']['must_not'].append(terms)
            else:
                if condition == "url": condition = "url.keyword"
                terms['terms'][condition] = param_values
                q['query']['bool']['filter']['bool']['must'].append(terms)

    if 'aggs' in params and params['aggs'] is not None:
        params['aggs'] = uri.decode(params['aggs'])
        if isinstance(params['aggs'], str):
            params['aggs'] = params['aggs'].split(',')

    if 'delta_only' in params and params['delta_only'] is not None:
        if params['delta_only'].lower() == "true" or params['delta_only'] == "1":
            params['delta_only'] = True

    if 'after' in params and params['after'] is not None:
        if LooksLikeInt(params['after']):
            params['after'] = int(params['after'])
        elif params['after'][-1:].lower() == "d":
            params['after'] = int(time.time()) - (int(params['after'][:-1]) * 86400)
        elif params['after'][-1:].lower() == "h":
            params['after'] = int(time.time()) - (int(params['after'][:-1]) * 3600)
        elif params['after'][-1:].lower() == "m":
            params['after'] = int(time.time()) - (int(params['after'][:-1]) * 60)
        elif params['after'][-1:].lower() == "s":
            params['after'] = int(time.time()) - (int(params['after'][:-1]))
        range = nested_dict()
        range['range']['created_utc']['gt'] = params['after']
        q['query']['bool']['filter']['bool']['must'].append(range)
        suggested_sort = "asc"
    else:
        params['after'] = None

    if 'before_id' in params and params['before_id'] is not None:
        range = nested_dict()
        range['range']['id']['lt'] = params['before_id']
        q['query']['bool']['filter']['bool']['must'].append(range)

    if 'before' in params and params['before'] is not None:
        if LooksLikeInt(params['before']):
            params['before'] = int(params['before'])
        elif params['before'][-1:].lower() == "d":
            params['before'] = int(time.time()) - (int(params['before'][:-1]) * 86400)
        elif params['before'][-1:].lower() == "h":
            params['before'] = int(time.time()) - (int(params['before'][:-1]) * 3600)
        elif params['before'][-1:].lower() == "m":
            params['before'] = int(time.time()) - (int(params['before'][:-1]) * 60)
        elif params['before'][-1:].lower() == "s":
            params['before'] = int(time.time()) - (int(params['before'][:-1]))
        range = nested_dict()
        range['range']['created_utc']['lt'] = params['before']
        q['query']['bool']['filter']['bool']['must'].append(range)
    else:
        params['before'] = None

    # Handle parameters that are range parameters (less than, greater than, equal to, etc.)
    conditions = ["reply_delay","score","num_comments","num_crossposts","nest_level"]
    for condition in conditions:
        if condition in params and params[condition] is not None:
            params[condition] = uri.decode(params[condition])
            if not isinstance(params[condition], (list, tuple)):
                params[condition] = [params[condition]]
            range = nested_dict()
            for p in params[condition]:
                range = nested_dict()
                if p[:1] == "<":
                    range['range'][condition]['lt'] = int(p[1:])
                elif p[:1] == ">":
                    range['range'][condition]['gt'] = int(p[1:])
                elif LooksLikeInt(p):
                    range['term'][condition] = int(p)
                q['query']['bool']['filter']['bool']['must'].append(range)

    # Handle boolean type conditions
    conditions = ["is_self","over_18","is_video","stickied","spoiler","locked","contest_mode","is_crosspostable","brand_safe"]
    for condition in conditions:
        if condition in params and params[condition] is not None:
            parameter = nested_dict()
            if params[condition].lower() == 'true' or params[condition] == "1":
                parameter['term'][condition] = "true" 
            elif params[condition].lower() == 'false' or params[condition] == "0":
                parameter['term'][condition] = "false"
            q['query']['bool']['filter']['bool']['must'].append(parameter)

    if 'sort_type' in params and params['sort_type'] is not None:
        params["sort_type"] = params['sort_type'].lower()
    else:
        params["sort_type"] = "created_utc"

    if 'limit' in params:
        params['size'] = params['limit']

    if 'size' in params and params['size'] is not None and LooksLikeInt(params['size']):
        size = 1000 if int(params['size']) > 1000 else int(params['size'])
        q['size'] = params['size'] = size
    else:
        q['size'] = params['size'] = 25

    if 'order' in params and params['order'] is not None:
        params['sort'] = params['order'].lower()

    if 'sort' in params and params['sort'] is not None:
        if ":" in params['sort']:
            params['sort_type'], params['sort'] = params['sort'].split(":")
        else:
            params['sort'] = params['sort'].lower()
        if params['sort'] != "asc" and params['sort'] != "desc":
            params['sort'] = suggested_sort
    else:
        params['sort'] = suggested_sort
    q['sort'][params['sort_type']] = params['sort']

    if 'frequency' in params and params['frequency'] is not None:
        if params['frequency'][-1:] in ['s','m','h','d','w','M','y'] and LooksLikeInt(params['frequency'][:1]):
            time_unit = params['frequency'][-1:]
            time_period = {'s':'second','m':'minute','h':'hour','d':'day','w':'week','M':'month','y':'year'}
            length = params['frequency'][:-1]
            params['frequency'] = str(length) + time_unit
        elif 'frequency' in params and params['frequency'].lower() in ['second','minute','hour','day','week','month','year']:
            params['frequency'] = params['frequency'].lower()
        else:
            params['frequency'] = None
    return(params,q)

