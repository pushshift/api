# Pushshift Reddit API Documentation

# Preface

The pushshift.io Reddit API was designed and created by the /r/datasets mod team to help provide enhanced functionality and search capabilities for searching Reddit comments and submissions.  The project lead, /u/stuck_in_the_matrix, is the maintainer of the Reddit comment and submissions archives located at https://files.pushshift.io.  

This RESTful API gives full functionality for searching Reddit data and also includes the capability of creating aggregations on the data.  With this API, you can quickly find the data that you are interested in and find interesting correlations within Reddit data.  

# Understanding the API

There are two main ways of accessing the Reddit comment and submission database.  One is using the API directly via https://api.pushshift.io/ and the other is by accessing the back-end Elasticsearch search engine directly via https://elastic.pushshift.io/  This document will explain both approaches and give examples on how to use the API as well as explain the parameters that can be used when doing a search.

# Using the https://api.pushshift.io endpoints

There are the two primary endpoints used to search all publically available comments and submissions on Reddit:

* /reddit/search/comment
* /reddit/search/submission

Let's start with searching for comments using the first endpoint.

# Searching Comments

To search for comments, use the endpoint https://api.pushshift.io/reddit/search/comment/ endpoint.  Let's start with a few examples and then go over the various parameters available when using this endpoint.  Do to a simple search, the q parameter is used to search for a specific word or phrase.  Here is an example:

**Search for the most recent comments mentioning the word "science"**
https://api.pushshift.io/reddit/search/comment/?q=science

This will search for the most recent comments with the word science in the body of the comment.  The search is not case-sensitive, so it will find any occurence of science regardless of capitalization.  The API defaults to sorting by the most recently made comments first.  After running this search, 25 results are returned.  This is the default size for searches and can be changed by using the size parameter.  This will be discussed in further detail in the paramaters section.  Data is returned in JSON format and results are included in the "data" key.  There is also a "metadata" key that gives additional information about the search including total number of results found, how long the search took to process, etc.  

# Search parameters for comments

There are numerous additional parameters that can be used when performing a comment search.  Let's go over each of them now and provide examples for each one.

| Parameter | Description | Default |
| ------ | ------ | ------- |
| q | Search term. | N/A |
| size | Number of results to return | 25 |
| fields | One return specific fields (comma delimited) | All Fields Returned
| sort | Return results "asc" or "desc" | "desc" |
| sort_type | Sort by a specific attribute | "created_utc" |
| aggs | Return aggregation data | N/A | 
| author | Restrict to a specific author | N/A |
| subreddit | Restrict to a specific subreddit | N/A | 
| after | Return results after this date | N/A |
| before | Return results before this date | N/A | 
| frequency | Used with the aggs parameter (See below) | N/A |

## Using the subreddit parameter

There are quite a few parameters to review, so let's start by providing some more complex examples and how to use the parameters above.  Let's continue with the previous example above and expand on our "science" keyword search.  What if we wanted to search for the term "science" but restrict it to a specific subreddit?  By using the subreddit parameter, we can do that:

**Search for the most recent comments mentioning the word "science" within the subreddit /r/askscience**
https://api.pushshift.io/reddit/search/comment/?q=science&subreddit=askscience

## Using the sort and size parameters

This will return 25 comments containing the term "science" but only from the /r/askscience subreddit.  Since we didn't ask for a specific sort method, the most recent comments are returned (the sort parameter defaults to "desc").  What if we wanted the first comment ever to /r/askscience that mentioned the word "science"?  We could use the sort and size parameters to handle that.

**Search for the most recent comments mentioning the word "science" within the subreddit /r/askscience**
https://api.pushshift.io/reddit/search/comment/?q=science&subreddit=askscience&sort=asc&size=1

This is the result:

```
{
    "data": [
        {
            "author": "MockDeath",
            "author_flair_css_class": null,
            "author_flair_text": null,
            "body": "Knowing more would definitely help.  I guess all you can do is find out if they know the basics like you said then take it from there.  That CO\u00b2 has the carbon turned to the isotope carbon14 in the upper atmosphere by cosmic radiation.  This causes a specific percentage of carbon in the atmosphere to be carbon14.\n\nNow we are carbon based life forms and we have to get the carbon we are built out of from some where.  We get it from eating plants, and the plants get it from absorbing CO\u00b2 from the air.  So so long as we are alive, we uptake new carbon14.  So this gives you a pretty good base line for dating.\n\nNow to fight arguments against carbon dating you could use the example of how we can see proton collisions in the LHC for sensitivity of our equipment.  Nuclear decay is very accurate in how fast it happens, this is why atomic clocks work to a much higher degree of accuracy than other methods of time keeping.  Also, you might want to make a general appeal for science.  Science works, that is why we have TV's, robots, particle accelerators, satellites, computers, MRI and CAT scanners, nuclear power, etc etc.  Scientists are not just willy nilly making shit up, or these kinds of things wouldn't work.",
            "created_utc": 1270637661,
            "id": "c0nn9iq",
            "link_id": "t3_bne3u",
            "parent_id": "t1_c0nn5ux",
            "score": 2,
            "subreddit": "askscience",
            "subreddit_id": "t5_2qm4e"
        }
    ],
    "metadata": {
        "execution_time_milliseconds": 30.52,
        "results_returned": 1,
        "shards": {
            "failed": 0,
            "successful": 36,
            "total": 36
        },
        "size": 1,
        "sort": "asc",
        "sort_type": "created_utc",
        "timed_out": false,
        "total_results": 134785,
        "version": "v3.0"
    }
}
```

From the result returned, we can see that the first comment ever made to /r/science mentioning "science" happened on epoch date 1270637661, which translates to Wednesday, April 7, 2010 10:54:21 AM (GMT).  Let's quickly go over the metadata pieces.  We can see that the execution time for this search was around 30 milliseconds.  There were a total of 36 shards searched and all were successful.  The search did not time out (timed_out parameter) which is good.  This is an attribute you may want to check if you use the API programmatically as some searches that are more complicated may sometimes time out.  The total_results value is 134,785.  This tells us the total number of comments in /r/askscience that mention the word science.  Since we did not use the before or after parameters, this number represents the entirity of the comments made to /r/askscience.

## Using before and after parameters 

Let's continue by using additional parameters to highlight the power of the search API.  The before and after parameters allow you to restrict the time-frame for the search by giving an epoch timestamp for both.  However, the API also understands more human-like values for the before and after parameters.  You can use a number followed by the characters s,m,h,d (which stand for second, minute, hour and day) to limit the time-frame as well.  Let's run through some examples.

If you wanted to do a search for "Rome" in the subreddit /r/askhistorians but limit it only to the past 30 days, you could use the after parameter with the value 30d (30 days).  

**Search the subreddit /r/askhistorians for comments mentioning Rome within the past 30 days**
https://api.pushshift.io/reddit/search/comment/?q=rome&subreddit=askhistorians&after=30d

What if there was a recent news story three days ago, but we wanted to limit the search window between 4 days ago and 2 days ago?  We could use both the before and after parameter to do so.  In the next example, we will search for comments mentioning Trump that were made between 4 and 2 days ago and sort by ascending.

**Search all subreddits for the term "Trump" and return comments made between 2 and 4 days ago**
https://api.pushshift.io/reddit/search/comment/?q=trump&after=4d&before=2d&sort=asc

## Using fields parameter

Let's say you wanted to do a search for the last 150 comments, but you only need the author and body fields returned for each comment.  Using the fields parameter, you can tell the API which pieces of information you want to filter.  This is primarily to help reduce bandwidth if you are making a lot of requests and only need specific fields returned.

Here is an example using the fields parameter to search for the past 150 comments that mention "government" and only returning the author and body fields:

**Search all subreddits for the term "government" and return comments with only the body and author keys**
https://api.pushshift.io/reddit/search/comment/?q=government&size=150&fields=body,author

## Using the author parameter

Using one of the examples above that searched for the first occurrence of the word "science" in the subreddit /r/askscience, we saw that the author of the comment was "MockDeath."  What if we wanted to get the first 100 comments that "MockDeath" made to Reddit?  We can use the author parameter, along with the sort and size parameters.

**Search all subreddits and get the first 100 comments ever made by the user /u/MockDeath**
https://api.pushshift.io/reddit/search/comment/?author=MockDeath&sort=asc&size=100





