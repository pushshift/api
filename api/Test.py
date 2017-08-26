import time
import html
from collections import defaultdict
import Parameters
from Helpers import *
import DBFunctions

class test:
    params = None
    def on_get(self, req, resp):
        data = {}
        data["data"] = "This is a test"
        #resp.cache_control = ["public","max-age=2","s-maxage=2"]
        #resp.body = json.dumps(data,sort_keys=True,indent=4, separators=(',', ': '))
        #print (req.context)
