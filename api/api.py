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
import User
import Parameters
from Helpers import *
from configparser import ConfigParser


api = falcon.API()
api.add_route('/reddit/search', Comment.search())
api.add_route('/reddit/comment/search', Comment.search())
api.add_route('/reddit/search/comment', Comment.search())
api.add_route('/reddit/search/submission', Submission.search())
api.add_route('/reddit/submission/search', Submission.search())
api.add_route('/reddit/analyze/user', User.Analyze())
api.add_route('/get/comment_ids/{submission_id}', Submission.getCommentIDs())
api.add_route('/reddit/submission/comment_ids/{submission_id}', Submission.getCommentIDs())
