################################################################## App Utilities
import os
from flask_bootstrap import Bootstrap
from flask import Flask, render_template, current_app, request, redirect, url_for, flash, session


####################################################################### Mongo DB

from flask_pymongo import PyMongo
from bson.objectid import ObjectId

#################################################################### Twitter API
import os
import env
import json
import tweepy                # REQUIRES PYTON 3.6, async won't work on 3.7
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy.streaming import StreamListener
from collections import Counter
from prettytable import PrettyTable
from operator import itemgetter



################################################################### APP SETTINGS ##############################################################

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY") 
Bootstrap(app)

### Mongo DB

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME") 
app.config["MONGO_URI"] = os.environ.get("MONGO_URI") 
mongo = PyMongo(app)

### Twitter Authentication

CONSUMER_KEY = os.environ.get("CONSUMER_KEY") 
CONSUMER_SECRET = os.environ.get("CONSUMER_SECRET") 
OAUTH_TOKEN = os.environ.get("OAUTH_TOKEN") 
OAUTH_TOKEN_SECRET = os.environ.get("OAUTH_TOKEN_SECRET") 

auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

api = tweepy.API(auth)



################################################################### VIEWS ######################################################################



############################################################## Home

@app.route('/')
@app.route('/interface')
def interface():
    
    return render_template("interface.html")
    
    
    
##################################################### Hashtag Search  

@app.route('/hashtag_search')
def hashtag_search():


    return render_template("hashtag_search.html")

@app.route('/tweets', methods=['POST'])
def tweets():
    
    harvest_tweets=mongo.db.harvest_tweets
    keyword = request.form.get('keyword')
    if keyword[0] != '#':
        keyword = '#' + keyword 
    count = int(request.form.get('count'))  
    
    
    tweet_data = [] 
    for tweet in tweepy.Cursor(api.search, q=keyword).items(count):
        data = {}
        data['text'] = tweet.text
        data['hashtag'] = keyword
        data['created_at'] = tweet.created_at
        data['location'] = tweet.user.location
        data['retweet_count'] = tweet.retweet_count
        tweet_data.append(data)
    
    session['tweet_data'] = tweet_data
    
    results = [status for status in tweepy.Cursor(api.search, q=keyword).items(count)]
    tweet_list = [[tweet._json['text'], tweet._json['created_at'][:19], tweet._json['user']['name'], tweet._json['retweet_count']]
                    for tweet in results]
              
        
    return render_template("tweets.html", tweet_list = tweet_list)    
    
    
@app.route('/upload_tweets', methods=['GET','POST'])
def upload_tweets():
    harvest_tweets=mongo.db.harvest_tweets
    
    tweet_data = session['tweet_data'] 

    for tweet in tweet_data:
        harvest_tweets.insert(tweet)

    return render_template("try.html", tweet_data = tweet_data) 
    
    
    
########################################## City Trends Intersection 

## http://www.woeidlookup.com/

@app.route('/twitter_trends')
def twitter_trends():
    
    message = ""
    return render_template("twitter_trends.html", message=message)
    
    
@app.route('/common_trends', methods=['GET','POST'])
def common_trends():
    
    city_1 = request.form.get('city_1')
    city_2 = request.form.get('city_2')
    
    try:
        city_1_trends = api.trends_place(city_1)
        city_2_trends = api.trends_place(city_2)
        
        # if city_1_trends and city_2_trends:
            
        city_1_trends_set = set([trend['name'] for trend in city_1_trends[0]['trends']])
        city_2_trends_set = set([trend['name'] for trend in city_2_trends[0]['trends']])
        
        common_trends = set.intersection(city_1_trends_set, city_2_trends_set)
        
        clean_trends = []
        for trend in common_trends:
            trend = trend.replace('#','')
            clean_trends.append(trend)
            
        clean_trends = sorted(clean_trends)
        
        return render_template("common_trends.html", clean_trends = clean_trends)    
    
    except:
    
        return render_template("twitter_trends.html", 
                              message="Requested ID does not exist, try another one:" )
        


################################################ Retweet popularity    

@app.route('/retweet_popularity')
def retweet_popularity():
    
    return render_template("retweet_popularity.html")    
    
    
@app.route('/most_retweets', methods=['POST'])
def most_retweets():
    
    keyword = request.form.get('keyword')
    count = int(request.form.get('count'))
    min_retweets = int(request.form.get('retweets'))
    
    ## get tweets for the search query

    results = [status for status in tweepy.Cursor(api.search, q=keyword).items(count)]
    
    
    pop_tweets = [status
                    for status in results
                        if status._json['retweet_count'] > min_retweets]
    
    ## tuple of tweet + retweet count                    
    tweet_list = [[tweet._json['text'], tweet._json['created_at'][:19], tweet._json['user']['name'], tweet._json['retweet_count']]
                    for tweet in pop_tweets]
                    
    ## sort descending
    most_popular_tweets = sorted(tweet_list, key=itemgetter(1), reverse=True)[:count]
    
    return render_template("most_retweets.html", most_popular_tweets = most_popular_tweets)
    
  
    
########################################### Acess Twitter Stream    
    
    
@app.route('/twitter_stream')
def twitter_stream():
    
    return render_template("twitter_stream.html")      
    
    
@app.route('/store_tweets', methods=['POST'])
def store_tweets():
    
    
    
    keywords = request.form.get('keyword')
    limit = int(request.form.get('limit'))
    
    keyword_list = keywords.split(',')
    
    
    class MyStreamListener(StreamListener):
    
        def __init__(self):
            super(MyStreamListener, self).__init__()
            self.num_tweets = 0
            
        def on_data(self, data):
            if self.num_tweets < limit: 
                self.num_tweets += 1
                try:
                    with open('tweet_mining.json', 'a') as tweet_file:
                        tweet_file.write(data)
                        return True
                except BaseException as e:
                    print("Failed %s"%str(e))
                return True 
            else:
                return False
            
        def on_error(self, status):
            print(status)
            return True

    ### ADD WAIT TIMER
    twitter_stream = Stream(auth, MyStreamListener())
    twitter_stream.filter(track=keyword_list)
    
 
    return render_template("try.html", keywords = keywords,
                               message="Tweets have been stored" )     



################################################################# APP INITIATION #############################################################


if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) 